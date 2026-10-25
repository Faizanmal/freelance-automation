"""Resend-verification: generic responses; DEBUG auto-verify only."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.auth import resend_verification
from app.schemas.user import ResendVerificationRequest


class ResendVerifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_resend_auto_verifies_when_smtp_missing_and_debug(self) -> None:
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
            is_production=False,
            debug=True,
            allow_dev_auth_helpers=True,
            email_smtp_host=None,
            public_app_url="http://localhost:3000",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch(
                "app.api.v1.auth.create_email_verification_token", return_value="tok"
            ),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            result = await resend_verification(
                request=MagicMock(),
                payload=ResendVerificationRequest(email="dev@example.com"),
                session=session,
                background_tasks=MagicMock(),
            )

        self.assertTrue(result["auto_verified"])
        self.assertTrue(user.is_verified)

    async def test_resend_is_generic_in_production_even_when_smtp_missing(self) -> None:
        user = SimpleNamespace(
            email="live@example.com",
            is_active=True,
            is_verified=False,
        )
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=user)
        settings = SimpleNamespace(
            is_production=True,
            debug=False,
            allow_dev_auth_helpers=False,
            email_smtp_host=None,
            public_app_url="https://app.example.com",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch(
                "app.api.v1.auth.create_email_verification_token", return_value="tok"
            ),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            result = await resend_verification(
                request=MagicMock(),
                payload=ResendVerificationRequest(email="live@example.com"),
                session=AsyncMock(),
                background_tasks=MagicMock(),
            )

        self.assertNotIn("verify_url", result)
        self.assertNotIn("auto_verified", result)
        self.assertIn("If that email is registered", result["detail"])

    async def test_resend_unknown_email_same_generic_body(self) -> None:
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=None)
        settings = SimpleNamespace(
            is_production=True,
            debug=False,
            allow_dev_auth_helpers=False,
            email_smtp_host="smtp.example.com",
            public_app_url="https://app.example.com",
        )

        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            result = await resend_verification(
                request=MagicMock(),
                payload=ResendVerificationRequest(email="missing@example.com"),
                session=AsyncMock(),
                background_tasks=MagicMock(),
            )

        self.assertEqual(
            result["detail"],
            "If that email is registered and unverified, we have sent a new verification link.",
        )
        self.assertNotIn("verify_url", result)


if __name__ == "__main__":
    unittest.main()
