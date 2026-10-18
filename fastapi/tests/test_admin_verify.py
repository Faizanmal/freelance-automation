"""Remaining: admin can mark users verified."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.admin import UserAdminUpdate, update_user


class AdminVerifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_can_set_is_verified(self) -> None:
        now = datetime.now(UTC)
        user = SimpleNamespace(
            id="u1",
            email="a@b.c",
            full_name="A",
            is_active=True,
            is_verified=False,
            is_superuser=False,
            is_totp_enabled=False,
            plan="free",
            subscription_status="inactive",
            timezone=None,
            locale=None,
            created_at=now,
            updated_at=now,
        )
        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = user
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result_proxy)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()

        admin = SimpleNamespace(is_superuser=True)
        updated = await update_user(
            user_id="u1",
            user_in=UserAdminUpdate(is_verified=True),
            current_user=admin,  # type: ignore[arg-type]
            session=session,
        )
        self.assertTrue(user.is_verified)
        self.assertTrue(updated.is_verified)
        session.commit.assert_awaited()

    async def test_admin_update_404_when_missing(self) -> None:
        from fastapi import HTTPException

        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = None
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result_proxy)

        with self.assertRaises(HTTPException) as ctx:
            await update_user(
                user_id="missing",
                user_in=UserAdminUpdate(is_verified=True),
                current_user=SimpleNamespace(is_superuser=True),  # type: ignore[arg-type]
                session=session,
            )
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
