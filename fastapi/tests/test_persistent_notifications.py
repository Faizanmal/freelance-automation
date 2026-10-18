"""P4: durable notification status is delivered / partial / failed."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.application.services.notification_service import (
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationResult,
)
from backend.application.services.persistent_notifications import (
    PersistentNotificationService,
)


class _FakeDispatcher:
    def __init__(self, results: list[NotificationResult]) -> None:
        self._results = results

    async def dispatch(self, payload: NotificationPayload) -> list[NotificationResult]:
        return self._results


class PersistentNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_mixed_channel_results_are_partial(self) -> None:
        record = SimpleNamespace(id=1, public_id="pub-1", status="sending")
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        # First add() captures the NotificationRecord we create.
        def _add(obj: object) -> None:
            if hasattr(obj, "status") and hasattr(obj, "public_id"):
                obj.id = 1  # type: ignore[attr-defined]
                nonlocal record
                record = obj  # type: ignore[assignment]

        session.add.side_effect = _add

        dispatcher = _FakeDispatcher(
            [
                NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    delivered=True,
                    message_id="m1",
                    error=None,
                ),
                NotificationResult(
                    channel=NotificationChannel.SLACK,
                    delivered=False,
                    message_id=None,
                    error="provider_not_configured",
                ),
            ]
        )
        service = PersistentNotificationService(session, dispatcher=dispatcher)  # type: ignore[arg-type]
        result = await service.send(
            NotificationPayload(
                user_id="u1",
                title="Match",
                body="Body",
                channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                priority=NotificationPriority.NORMAL,
            )
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["delivered_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(record.status, "partial")

    async def test_all_failed_is_failed(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        def _add(obj: object) -> None:
            if hasattr(obj, "status"):
                obj.id = 2  # type: ignore[attr-defined]

        session.add.side_effect = _add
        dispatcher = _FakeDispatcher(
            [
                NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    delivered=False,
                    error="provider_not_configured",
                )
            ]
        )
        service = PersistentNotificationService(session, dispatcher=dispatcher)  # type: ignore[arg-type]
        result = await service.send(
            NotificationPayload(
                user_id="u1",
                title="Match",
                body="Body",
                channels=[NotificationChannel.EMAIL],
            )
        )
        self.assertEqual(result["status"], "failed")


if __name__ == "__main__":
    unittest.main()
