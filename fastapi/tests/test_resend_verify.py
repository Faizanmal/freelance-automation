"""Remaining: resend-verification auto-verifies in non-prod when SMTP is down."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.auth import resend_verification
from app.schemas.user import ResendVerificationRequest


class ResendVerifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_resend_auto_verifies_when_smtp_missing_non_prod(self) -> None:
        user = SimpleNamespace(
            email="dev@example.com",
            is_active=True,
            is_verified=False,
        )
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=user)
        session = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        settings = SimpleNamespace(
            is_production=False, public_app_url="http://localhost:3000"
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch(
                "app.api.v1.auth.create_email_verification_token", return_value="tok"
            ),
            patch(
                "app.api.v1.auth.EmailService.send_verification_email",
                return_value=False,
            ),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            result = await resend_verification(
                request=MagicMock(),
                payload=ResendVerificationRequest(email="dev@example.com"),
                session=session,
            )

        self.assertTrue(result["auto_verified"])
        self.assertTrue(user.is_verified)


if __name__ == "__main__":
    unittest.main()
