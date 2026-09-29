from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from app.core.logging.logger import get_logger
from app.core.security.jwt import create_access_token, create_password_reset_token, decode_password_reset_token, create_email_verification_token, decode_email_verification_token, decode_access_token
from app.core.security.rate_limit import auth_rate_limiter, client_ip
from app.core.security.blocklist import blocklist
from app.api.dependencies import security
from app.schemas.token import Token
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest, UserCreate, UserRead, VerifyEmailRequest, ResendVerificationRequest
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.email_service import EmailService
from backend.application.services.user_service import UserService
from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from config.settings import get_settings
from database.core.session import get_db
from database.models.preference import UserPreferences
from fastapi import APIRouter, Depends, HTTPException, Request, status

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> Token:
    await auth_rate_limiter.check(f"login:{client_ip(request)}", limit=20, window_seconds=60)
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    user = await service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    expires_delta = timedelta(minutes=get_settings().access_token_expire_minutes)
    access_token = create_access_token(str(user.id), expires_delta=expires_delta)
    return Token(
        access_token=access_token,
        expires_at=datetime.now(timezone.utc) + expires_delta,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user_create: UserCreate,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserRead:
    await auth_rate_limiter.check(f"register:{client_ip(request)}", limit=10, window_seconds=3600)
    repository = SQLAlchemyUserRepository(session)
    existing = await repository.get_by_email(user_create.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    service = UserService(repository)
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
    
    verification_token = create_email_verification_token(user.email)
    EmailService.send_verification_email(user.email, verification_token)
    
    return UserRead.model_validate(user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    await auth_rate_limiter.check(f"forgot:{client_ip(request)}", limit=5, window_seconds=3600)
    repository = SQLAlchemyUserRepository(session)
    user = await repository.get_by_email(payload.email)
    
    if user and user.is_active:
        token = create_password_reset_token(user.email)
        EmailService.send_password_reset_email(user.email, token)
        
    return {"detail": "If that email is registered, we have sent a reset link."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    await auth_rate_limiter.check(f"reset:{client_ip(request)}", limit=5, window_seconds=3600)
    
    try:
        email = decode_password_reset_token(payload.token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    success = await service.update_password(email, payload.new_password)
    
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not reset password")
        
    return {"detail": "Password has been successfully reset."}


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    await auth_rate_limiter.check(f"verify:{client_ip(request)}", limit=10, window_seconds=3600)
    
    try:
        email = decode_email_verification_token(payload.token)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    success = await service.verify_email(email)
    
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not verify email")
        
    return {"detail": "Email has been successfully verified."}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    await auth_rate_limiter.check(f"resend:{client_ip(request)}", limit=3, window_seconds=3600)
    repository = SQLAlchemyUserRepository(session)
    user = await repository.get_by_email(payload.email)
    
    if user and user.is_active and not user.is_verified:
        token = create_email_verification_token(user.email)
        EmailService.send_verification_email(user.email, token)
        
    return {"detail": "If that email is registered and unverified, we have sent a new verification link."}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> None:
    if not credentials:
        return
        
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            exp_time = datetime.fromtimestamp(exp, timezone.utc)
            await blocklist.block_token(jti, exp_time)
    except jwt.InvalidTokenError:
        pass
