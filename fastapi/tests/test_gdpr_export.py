from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.users import export_current_user_data


class GdprExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_gdpr_export_returns_all_user_data(self) -> None:
        now = datetime.now(UTC)
        current_user = SimpleNamespace(
            id="usr-123",
            email="freelancer@example.com",
            full_name="Jane Doe",
            plan="pro",
            subscription_status="active",
            is_active=True,
            is_verified=True,
            created_at=now,
        )

        pref_obj = SimpleNamespace(
            keywords=["fastapi", "react"],
            exclude_keywords=["unpaid"],
            skills=["python"],
            experience_level="senior",
            min_budget=1000.0,
            max_budget=5000.0,
            min_hourly_rate=65.0,
            sources=["remoteok"],
            match_threshold=0.4,
            notification_channels=["email"],
            digest_mode=True,
            freelance_focus=True,
            location="Remote",
            timezone="America/New_York",
            digest_days=["mon", "wed", "fri"],
            digest_time_local="09:00",
            destinations={"email": "freelancer@example.com"},
        )

        lead_action = SimpleNamespace(
            job_id=42,
            status="save",
            created_at=now,
        )

        job_app = SimpleNamespace(
            id=1,
            job_id=42,
            source_name="remoteok",
            status="pending",
            proposal="Hi, I am interested in building your FastAPI API.",
            bid_amount=2500.0,
            created_at=now,
        )

        notif = SimpleNamespace(
            public_id="notif-1",
            title="3 new Python leads found",
            body="Here are top fits for your rules.",
            channels=["email"],
            status="delivered",
            created_at=now,
        )

        # Mock query results
        session = AsyncMock()

        pref_res = MagicMock()
        pref_res.scalar_one_or_none.return_value = pref_obj

        actions_res = MagicMock()
        actions_res.scalars.return_value.all.return_value = [lead_action]

        apps_res = MagicMock()
        apps_res.scalars.return_value.all.return_value = [job_app]

        notifs_res = MagicMock()
        notifs_res.scalars.return_value.all.return_value = [notif]

        session.execute.side_effect = [pref_res, actions_res, apps_res, notifs_res]

        data = await export_current_user_data(current_user=current_user, session=session)  # type: ignore[arg-type]

        self.assertIn("exported_at", data)
        self.assertEqual(data["user"]["id"], "usr-123")
        self.assertEqual(data["user"]["email"], "freelancer@example.com")
        self.assertEqual(data["preferences"]["keywords"], ["fastapi", "react"])
        self.assertEqual(data["preferences"]["min_hourly_rate"], 65.0)
        self.assertEqual(len(data["lead_actions"]), 1)
        self.assertEqual(data["lead_actions"][0]["job_id"], 42)
        self.assertEqual(len(data["applications"]), 1)
        self.assertEqual(data["applications"][0]["bid_amount"], 2500.0)
        self.assertEqual(len(data["notifications"]), 1)
        self.assertEqual(data["notifications"][0]["public_id"], "notif-1")


if __name__ == "__main__":
    unittest.main()

