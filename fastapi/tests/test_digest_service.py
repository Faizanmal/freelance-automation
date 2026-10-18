"""Show-clock digest due checks."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from backend.application.services.digest_service import is_digest_due


class DigestDueTests(unittest.TestCase):
    def test_due_on_weekday_near_local_time(self) -> None:
        # Wednesday 2026-10-14 09:05 America/New_York
        local = datetime(2026, 10, 14, 9, 5, tzinfo=ZoneInfo("America/New_York"))
        prefs = SimpleNamespace(
            digest_mode=True,
            timezone="America/New_York",
            digest_days=["mon", "tue", "wed", "thu", "fri"],
            digest_time_local="09:00",
            digest_last_sent_at=None,
        )
        self.assertTrue(is_digest_due(prefs, now_local=local, window_minutes=20))

    def test_not_due_wrong_day(self) -> None:
        local = datetime(2026, 10, 17, 9, 5, tzinfo=ZoneInfo("UTC"))  # Saturday
        prefs = SimpleNamespace(
            digest_mode=True,
            timezone="UTC",
            digest_days=["mon", "tue", "wed", "thu", "fri"],
            digest_time_local="09:00",
            digest_last_sent_at=None,
        )
        self.assertFalse(is_digest_due(prefs, now_local=local))

    def test_not_due_when_already_sent_today(self) -> None:
        local = datetime(2026, 10, 14, 9, 5, tzinfo=ZoneInfo("UTC"))
        prefs = SimpleNamespace(
            digest_mode=True,
            timezone="UTC",
            digest_days=["wed"],
            digest_time_local="09:00",
            digest_last_sent_at=datetime(2026, 10, 14, 9, 0, tzinfo=UTC),
        )
        self.assertFalse(is_digest_due(prefs, now_local=local))

    def test_digest_mode_off_skips(self) -> None:
        local = datetime(2026, 10, 14, 9, 5, tzinfo=ZoneInfo("UTC"))
        prefs = SimpleNamespace(
            digest_mode=False,
            timezone="UTC",
            digest_days=["wed"],
            digest_time_local="09:00",
            digest_last_sent_at=None,
        )
        self.assertFalse(is_digest_due(prefs, now_local=local))


if __name__ == "__main__":
    unittest.main()
