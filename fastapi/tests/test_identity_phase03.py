"""Phase 03 identity: anti-enumeration register, OAuth link policy, roles."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.dependencies import require_roles
from app.api.v1.auth import register
from app.schemas.user import UserCreate
from backend.application.services.user_service import AccountLinkError, UserService
from fastapi import HTTPException


class RegisterAntiEnumerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_email_does_not_409(self) -> None:
        existing = SimpleNamespace(
            id="u1",
            email="taken@example.com",
            full_name="Taken",
            is_verified=True,
        )
        session = AsyncMock()
        session.commit = AsyncMock()
        repo = MagicMock()
        repo.get_by_email = AsyncMock(return_value=existing)
        settings = SimpleNamespace(
            allow_dev_auth_helpers=False,
            email_smtp_host=None,
            resend_api_key=None,
            public_app_url="http://localhost:3000",
        )
        with (
            patch("app.api.v1.auth.auth_rate_limiter.check", new=AsyncMock()),
            patch("app.api.v1.auth.client_ip", return_value="127.0.0.1"),
            patch("app.api.v1.auth.SQLAlchemyUserRepository", return_value=repo),
            patch("app.api.v1.auth.get_settings", return_value=settings),
            patch("app.api.v1.auth.record_audit", new=AsyncMock()),
        ):
            result = await register(
                request=MagicMock(),
                user_create=UserCreate(
                    email="taken@example.com",
                    password="password123",
                    full_name="Nope",
                ),
                session=session,
                background_tasks=MagicMock(),
            )
        self.assertFalse(result.created)
        self.assertIsNone(result.user)
        self.assertIn("inbox", result.detail.lower())


class OAuthLinkPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_unverified_local_account_raises(self) -> None:
        repo = MagicMock()
        repo.get_by_google_id = AsyncMock(return_value=None)
        repo.get_by_email = AsyncMock(
            return_value=SimpleNamespace(
                id="u",
                email="a@b.com",
                is_verified=False,
                google_id=None,
                full_name=None,
            )
        )
        service = UserService(repo)
        with self.assertRaises(AccountLinkError):
            await service.authenticate_or_create_google_user(
                google_id="g1", email="a@b.com", full_name="A"
            )


class RoleGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_require_roles_blocks_wrong_role(self) -> None:
        checker = require_roles("staff")
        user = SimpleNamespace(is_superuser=False, account_role="freelancer")
        with self.assertRaises(HTTPException) as ctx:
            await checker(current_user=user)
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_superuser_bypasses_role_gate(self) -> None:
        checker = require_roles("staff")
        user = SimpleNamespace(is_superuser=True, account_role="freelancer")
        out = await checker(current_user=user)
        self.assertIs(out, user)


if __name__ == "__main__":
    unittest.main()
