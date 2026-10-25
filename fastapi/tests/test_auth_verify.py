"""P2: local auto-verify / dev-verify gates when SMTP is unavailable."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.auth import dev_verify_current_user, register
from app.schemas.user import UserCreate

from fastapi import HTTPException


def _user(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    base = {
        "id": "u1",
        "email": "dev@example.com",
        "full_name": "Dev",
        "is_active": True,
        "is_verified": False,
        "is_superuser": False,
        "is_totp_enabled": False,
        "plan": "free",
        "subscription_status": "inactive",
        "timezone": None,
        "locale": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class AuthVerifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_auto_verifies_when_smtp_missing_and_debug(self) -> None:
        created = _user()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()

        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=None)

        service = MagicMock()
        service.create_user = AsyncMock(return_value=created)

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
            patch("app.api.v1.auth.UserService", return_value=service),
            patch(
                "app.api.v1.auth.create_email_verification_token", return_value="tok"
            ),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            result = await register(
                request=MagicMock(),
                user_create=UserCreate(
                    email="dev@example.com",
                    password="password123",
                    full_name="Dev",
                ),
                session=session,
                background_tasks=MagicMock(),
            )

        self.assertTrue(result.auto_verified)
        self.assertFalse(result.verification_email_sent)
        self.assertTrue(created.is_verified)
        self.assertIn("auto-verified", (result.detail or "").lower())
        self.assertTrue(result.verify_url)

    async def test_register_does_not_leak_verify_url_in_production(self) -> None:
        created = _user()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()

        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=None)
        service = MagicMock()
        service.create_user = AsyncMock(return_value=created)
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
            patch("app.api.v1.auth.UserService", return_value=service),
            patch(
                "app.api.v1.auth.create_email_verification_token", return_value="tok"
            ),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            result = await register(
                request=MagicMock(),
                user_create=UserCreate(
                    email="dev@example.com",
                    password="password123",
                    full_name="Dev",
                ),
                session=session,
                background_tasks=MagicMock(),
            )

        self.assertFalse(result.auto_verified or False)
        self.assertFalse(created.is_verified)
        self.assertIsNone(result.verify_url)

    async def test_register_queues_email_when_smtp_configured(self) -> None:
        created = _user()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=None)
        service = MagicMock()
        service.create_user = AsyncMock(return_value=created)
        background = MagicMock()
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
            patch("app.api.v1.auth.UserService", return_value=service),
            patch(
                "app.api.v1.auth.create_email_verification_token", return_value="tok"
            ),
            patch("app.api.v1.auth.get_settings", return_value=settings),
        ):
            result = await register(
                request=MagicMock(),
                user_create=UserCreate(
                    email="dev@example.com",
                    password="password123",
                    full_name="Dev",
                ),
                session=session,
                background_tasks=background,
            )

        background.add_task.assert_called_once()
        self.assertTrue(result.verification_email_sent)
        self.assertIsNone(result.verify_url)

    async def test_dev_verify_blocked_without_debug_flag(self) -> None:
        settings = SimpleNamespace(
            is_production=False, debug=False, allow_dev_auth_helpers=False
        )
        user = _user()
        with (
            patch("app.api.v1.auth.get_settings", return_value=settings),
            self.assertRaises(HTTPException) as ctx,
        ):
            await dev_verify_current_user(session=AsyncMock(), current_user=user)  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_dev_verify_marks_user_when_debug(self) -> None:
        settings = SimpleNamespace(
            is_production=False, debug=True, allow_dev_auth_helpers=True
        )
        user = _user()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()

        with patch("app.api.v1.auth.get_settings", return_value=settings):
            result = await dev_verify_current_user(session=session, current_user=user)  # type: ignore[arg-type]

        self.assertTrue(result["is_verified"])
        self.assertTrue(user.is_verified)
        session.commit.assert_awaited()


if __name__ == "__main__":
    unittest.main()
