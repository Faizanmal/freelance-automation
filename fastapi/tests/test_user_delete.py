"""Account delete must clear child rows before removing the user."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


class UserDeleteTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_clears_owned_rows_before_user(self) -> None:
        session = AsyncMock()
        # First execute: select notification ids; remaining: deletes.
        notification_result = MagicMock()
        notification_result.scalars.return_value.all.return_value = [11, 12]
        session.execute = AsyncMock(return_value=notification_result)
        session.delete = AsyncMock()
        session.commit = AsyncMock()

        repo = SQLAlchemyUserRepository(session)
        user = SimpleNamespace(id="user-1")

        await repo.delete(user)  # type: ignore[arg-type]

        # select notification ids + delete deliveries + 4 child deletes
        self.assertEqual(session.execute.await_count, 6)
        session.delete.assert_awaited_once_with(user)
        session.commit.assert_awaited_once()

        statements = [str(call.args[0]) for call in session.execute.await_args_list]
        self.assertTrue(any("notifications" in s for s in statements))
        self.assertTrue(any("user_lead_actions" in s for s in statements))
        self.assertTrue(any("job_applications" in s for s in statements))
        self.assertTrue(any("user_preferences" in s for s in statements))


if __name__ == "__main__":
    unittest.main()
