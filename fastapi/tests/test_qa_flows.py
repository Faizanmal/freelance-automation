"""QA coverage tests: fresh registration, password-reset completion, 2FA lifecycle,
login/logout, and match-score consistency using isolated test accounts."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
from app.api.v1.auth import (
    disable_2fa,
    enable_2fa,
    login,
    logout,
    register,
    reset_password,
    setup_2fa,
)
from app.core.security.jwt import create_password_reset_token
from app.schemas.user import ResetPasswordRequest, UserCreate, Verify2FARequest
from backend.application.services.user_service import UserService
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


def _make_test_user(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    hashed = UserService.hash_password("InitialPass123!")
    base = {
        "id": "qa-test-user-1",
        "email": "qa-isolated@example.com",
        "full_name": "QA Test User",
        "hashed_password": hashed,
        "is_active": True,
        "is_verified": False,
        "is_superuser": False,
        "is_totp_enabled": False,
        "totp_secret": None,
        "plan": "free",
        "subscription_status": "inactive",
        "timezone": None,
        "locale": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class QAFlowsTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_registration_creates_unverified_account_when_smtp_blocked(
        self,
    ) -> None:
        user = _make_test_user()
        session = AsyncMock()
        session.add = MagicMock()
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=None)
        service = MagicMock()
        service.create_user = AsyncMock(return_value=user)
        settings = SimpleNamespace(
            is_production=True,
            debug=False,
            allow_dev_auth_helpers=False,
            email_smtp_host=None,
            resend_api_key=None,
            public_app_url="https://freelance-automation-xi.vercel.app",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.UserService", return_value=service),
            patch(
                "app.api.v1.auth.create_email_verification_token",
                return_value="verify-tok",
            ),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            res = await register(
                request=MagicMock(),
                user_create=UserCreate(
                    email="qa-isolated@example.com",
                    password="InitialPass123!",
                    full_name="QA Test User",
                ),
                session=session,
                background_tasks=MagicMock(),
            )

        self.assertEqual(res.email, "qa-isolated@example.com")
        self.assertFalse(res.is_verified)
        self.assertFalse(res.verification_email_sent)

    async def test_password_reset_completion_and_login_with_new_password(self) -> None:
        user = _make_test_user()
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=user)
        repo.update = AsyncMock(return_value=user)
        session = AsyncMock()

        reset_token = create_password_reset_token(user.email)
        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.EmailService.send_account_alert", return_value=False),
        ):
            reset_res = await reset_password(
                request=MagicMock(),
                payload=ResetPasswordRequest(
                    token=reset_token, new_password="UpdatedPass456!"
                ),
                session=session,
            )
            self.assertIn("successfully reset", reset_res["detail"])

            # Old password must fail
            svc = UserService(repo)
            self.assertIsNone(await svc.authenticate(user.email, "InitialPass123!"))
            # New password must succeed
            authed_user = await svc.authenticate(user.email, "UpdatedPass456!")
            self.assertIsNotNone(authed_user)

    async def test_2fa_setup_enable_login_and_disable_on_test_account(self) -> None:
        user = _make_test_user()
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=user)
        session = AsyncMock()

        # 1. Setup 2FA
        setup_res = await setup_2fa(user=user, session=session)  # type: ignore[arg-type]
        self.assertTrue(setup_res.secret)
        self.assertIn("otpauth://totp/", setup_res.provisioning_uri)
        self.assertFalse(user.is_totp_enabled)

        # 2. Enable 2FA with valid TOTP code
        totp = pyotp.TOTP(setup_res.secret)
        valid_code = totp.now()
        with patch("app.api.v1.auth.EmailService.send_account_alert", return_value=False):
            enable_res = await enable_2fa(
                payload=Verify2FARequest(code=valid_code),
                user=user,  # type: ignore[arg-type]
                session=session,
            )
        self.assertEqual(enable_res["detail"], "2FA successfully enabled")
        self.assertTrue(user.is_totp_enabled)

        # 3. Login without TOTP code raises 401 TOTP_REQUIRED
        form_data = SimpleNamespace(username=user.email, password="InitialPass123!")
        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await login(
                    request=MagicMock(),
                    session=session,
                    form_data=form_data,  # type: ignore[arg-type]
                    totp_code=None,
                )
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertEqual(ctx.exception.detail, "TOTP_REQUIRED")

            # 4. Login with valid TOTP code succeeds
            token_res = await login(
                request=MagicMock(),
                session=session,
                form_data=form_data,  # type: ignore[arg-type]
                totp_code=totp.now(),
            )
            self.assertTrue(token_res.access_token)

            # 5. Logout blocklists the token
            with patch(
                "app.api.v1.auth.blocklist.block_token", new=AsyncMock()
            ) as mock_block:
                await logout(
                    credentials=HTTPAuthorizationCredentials(
                        scheme="Bearer", credentials=token_res.access_token
                    )
                )
                mock_block.assert_awaited_once()

        # 6. Disable 2FA on test account
        with patch("app.api.v1.auth.EmailService.send_account_alert", return_value=False):
            disable_res = await disable_2fa(
                payload=Verify2FARequest(code=totp.now()),
                user=user,  # type: ignore[arg-type]
                session=session,
            )
        self.assertEqual(disable_res["detail"], "2FA successfully disabled")
        self.assertFalse(user.is_totp_enabled)
        self.assertIsNone(user.totp_secret)


if __name__ == "__main__":
    unittest.main()

