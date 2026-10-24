from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pyotp
from app.api.dependencies import get_current_user, security
from app.core.logging.logger import get_logger
from app.core.security.blocklist import blocklist
from app.core.security.jwt import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    decode_access_token,
    decode_email_verification_token,
    decode_password_reset_token,
)
from app.core.security.rate_limit import auth_rate_limiter, client_ip
from app.schemas.token import Token
from app.schemas.user import (
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    Setup2FAResponse,
    UserCreate,
    UserRead,
    Verify2FARequest,
    VerifyEmailRequest,
)
from fastapi.security import HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.email_service import EmailService
from backend.application.services.user_service import UserService
from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from config.settings import get_settings
from database.core.session import get_db
from database.models.preference import UserPreferences
from database.models.user import User
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    totp_code: str | None = Form(None),
) -> Token:
    await auth_rate_limiter.check(
        f"login:{client_ip(request)}", limit=20, window_seconds=60
    )
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    user = await service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    if user.is_totp_enabled:
        if not totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="TOTP_REQUIRED"
            )

        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code"
            )

    expires_delta = timedelta(minutes=get_settings().access_token_expire_minutes)
    access_token = create_access_token(str(user.id), expires_delta=expires_delta)
    return Token(
        access_token=access_token,
        expires_at=datetime.now(UTC) + expires_delta,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user_create: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    await auth_rate_limiter.check(
        f"register:{client_ip(request)}", limit=10, window_seconds=3600
    )
    repository = SQLAlchemyUserRepository(session)
    existing = await repository.get_by_email(user_create.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    service = UserService(repository)
    try:
        user = await service.create_user(
            email=user_create.email,
            password=user_create.password,
            full_name=user_create.full_name,
        )
        prefs = UserPreferences(
            user_id=user.id,
            keywords=["python", "fastapi", "react", "typescript"],
            exclude_keywords=[],
            sources=[],
            notification_channels=["email"],
            match_threshold=0.35,
            digest_mode=False,
            alert_email=user.email,
        )
        session.add(prefs)
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from None

    settings = get_settings()
    verification_token = create_email_verification_token(user.email)
    # Email failures must never fail signup.
    verify_sent = False
    try:
        verify_sent = EmailService.send_verification_email(
            user.email, verification_token
        )
    except Exception:
        logger.exception("Verification email raised for %s", user.email)
    try:
        EmailService.send_welcome_email(user.email, user.full_name)
    except Exception:
        logger.exception("Welcome email raised for %s", user.email)

    auto_verified = False
    verify_url: str | None = None
    # Local/dev without SMTP: auto-verify so scrape→match→apply is usable.
    if not verify_sent and not settings.is_production:
        user.is_verified = True
        session.add(user)
        await session.commit()
        await session.refresh(user)
        auto_verified = True
        logger.info(
            "Auto-verified %s in non-production (SMTP not configured)", user.email
        )
    elif not verify_sent:
        logger.warning(
            "Verification email not delivered for %s — configure EMAIL_SMTP_*",
            user.email,
        )
        verify_url = (
            f"{settings.public_app_url.rstrip('/')}/auth/verify?token={verification_token}"
        )

    read = UserRead.model_validate(user)
    if auto_verified:
        detail = "Account created and auto-verified for local development (SMTP not configured)."
    elif verify_sent:
        detail = "Account created. Check your inbox to verify email before scraping."
    else:
        detail = (
            "Account created, but the verification email was not delivered. "
            "Configure EMAIL_SMTP_* then use resend-verification."
        )
    return read.model_copy(
        update={
            "verification_email_sent": verify_sent,
            "auto_verified": auto_verified,
            "verify_url": verify_url,
            "detail": detail,
        }
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    await auth_rate_limiter.check(
        f"forgot:{client_ip(request)}", limit=5, window_seconds=3600
    )
    repository = SQLAlchemyUserRepository(session)
    user = await repository.get_by_email(payload.email)

    if user and user.is_active:
        token = create_password_reset_token(user.email)
        sent = EmailService.send_password_reset_email(user.email, token)
        if not sent:
            logger.warning("Password reset email not delivered for %s", user.email)
            return {
                "detail": "Account found, but email could not be delivered. Configure EMAIL_SMTP_* and try again.",
                "email_delivered": False,
            }
        return {
            "detail": "If that email is registered, we have sent a reset link.",
            "email_delivered": True,
        }

    return {
        "detail": "If that email is registered, we have sent a reset link.",
        "email_delivered": None,
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    await auth_rate_limiter.check(
        f"reset:{client_ip(request)}", limit=5, window_seconds=3600
    )

    try:
        email = decode_password_reset_token(payload.token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    success = await service.update_password(email, payload.new_password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not reset password"
        )

    EmailService.send_account_alert(
        email,
        "Your Signal Desk password was changed",
        "Your password was just reset. If you did not do this, reset it again and contact support@signaldesk.com.",
    )
    return {"detail": "Password has been successfully reset."}


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    await auth_rate_limiter.check(
        f"verify:{client_ip(request)}", limit=10, window_seconds=3600
    )

    try:
        email = decode_email_verification_token(payload.token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    success = await service.verify_email(email)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not verify email"
        )

    return {"detail": "Email has been successfully verified."}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    await auth_rate_limiter.check(
        f"resend:{client_ip(request)}", limit=3, window_seconds=3600
    )
    repository = SQLAlchemyUserRepository(session)
    user = await repository.get_by_email(payload.email)

    settings = get_settings()
    sent = False
    if user and user.is_active and not user.is_verified:
        token = create_email_verification_token(user.email)
        sent = EmailService.send_verification_email(user.email, token)
        if not sent and not settings.is_production:
            user.is_verified = True
            session.add(user)
            await session.commit()
            return {
                "detail": "SMTP unavailable — account auto-verified for local development.",
                "email_delivered": False,
                "auto_verified": True,
            }
        if not sent:
            return {
                "detail": "Account found, but email could not be delivered. Configure EMAIL_SMTP_* and try again.",
                "email_delivered": False,
                "verify_url": f"{settings.public_app_url.rstrip('/')}/auth/verify?token={token}",
            }

    return {
        "detail": "If that email is registered and unverified, we have sent a new verification link.",
        "email_delivered": (
            sent if user and user.is_active and not user.is_verified else None
        ),
    }


@router.post("/dev-verify")
async def dev_verify_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """Mark the signed-in user verified when SMTP is unavailable (non-production only)."""
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.is_verified:
        return {"detail": "Already verified.", "is_verified": True}
    current_user.is_verified = True
    session.add(current_user)
    await session.commit()
    return {
        "detail": "Email marked verified for local development.",
        "is_verified": True,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> None:
    if not credentials:
        return

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            exp_time = datetime.fromtimestamp(exp, UTC)
            await blocklist.block_token(jti, exp_time)
    except jwt.InvalidTokenError:
        pass


@router.post(
    "/2fa/setup", response_model=Setup2FAResponse, status_code=status.HTTP_200_OK
)
async def setup_2fa(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Setup2FAResponse:
    if user.is_totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is already enabled"
        )

    secret = pyotp.random_base32()
    user.totp_secret = secret
    await session.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.email, issuer_name="Freelance Intelligence"
    )

    return Setup2FAResponse(secret=secret, provisioning_uri=provisioning_uri)


@router.post("/2fa/enable", status_code=status.HTTP_200_OK)
async def enable_2fa(
    payload: Verify2FARequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    if user.is_totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is already enabled"
        )
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA setup not initiated"
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code"
        )

    user.is_totp_enabled = True
    await session.commit()

    EmailService.send_account_alert(
        user.email,
        "Two-factor authentication was enabled",
        "TOTP was just turned on for your Signal Desk account. If this was not you, reset your password.",
    )
    return {"detail": "2FA successfully enabled"}


@router.post("/2fa/disable", status_code=status.HTTP_200_OK)
async def disable_2fa(
    payload: Verify2FARequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    if not user.is_totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is not enabled"
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code"
        )

    user.is_totp_enabled = False
    user.totp_secret = None
    await session.commit()

    EmailService.send_account_alert(
        user.email,
        "Two-factor authentication was disabled",
        "TOTP was just turned off for your Signal Desk account. If this was not you, reset your password.",
    )
    return {"detail": "2FA successfully disabled"}
