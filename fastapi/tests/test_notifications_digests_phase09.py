"""Comprehensive test suite for Phase 09 — Reliable alerts, scheduled digests, and user-controlled automation.

Covers:
1. Duplicate scheduler execution & restart idempotency (no duplicate digest).
2. Bounded retries and dead-letter queue.
3. IANA timezone validation & DST transitions (spring-forward gap, fall-back duplicate).
4. Quiet hours suppression (overnight & daytime).
5. Unsubscribed and paused user protection.
6. Webhook bounce / complaint / unsubscribe processing & sender reputation safeguards.
7. Source outage resilience (scrapers down does not crash digest).
8. Expired and stale listing exclusion before send.
9. Provider downtime, degradation, and honesty (no fake success).
10. Cross-user access prevention (inbox isolation).
11. Provider status observability without recipient PII.
12. Digest preview and test send to verified user.
13. Source diversity balancing.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from backend.application.services.digest_scheduler import (
    calculate_next_send,
    is_digest_due,
    is_in_quiet_hours,
    parse_digest_days,
    parse_local_time,
    validate_iana_timezone,
)
from backend.application.services.digest_service import DigestSelector, DigestService
from backend.application.services.immediate_alerts import ImmediateAlertService
from backend.application.services.notification_service import (
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationService,
)
from backend.application.services.outbox_service import OutboxService
from database.models.job import JobRecord
from database.models.notification import (
    DigestSentJob,
    NotificationOutbox,
    NotificationRecord,
)
from database.models.preference import UserPreferences
from database.models.user import User


class NotificationsPhase09Tests(unittest.IsolatedAsyncioTestCase):
    # ---------------------------------------------------------------------
    # 1. IANA Timezone & DST Resilience
    # ---------------------------------------------------------------------
    def test_iana_timezone_validation(self) -> None:
        self.assertEqual(validate_iana_timezone("America/New_York"), "America/New_York")
        self.assertEqual(validate_iana_timezone("Europe/London"), "Europe/London")
        self.assertEqual(validate_iana_timezone("Asia/Tokyo"), "Asia/Tokyo")
        self.assertEqual(validate_iana_timezone("UTC"), "UTC")
        self.assertEqual(validate_iana_timezone(""), "UTC")
        self.assertEqual(validate_iana_timezone(None), "UTC")

        with self.assertRaises(ValueError):
            validate_iana_timezone("Mars/Olympus_Mons")

        with self.assertRaises(ValueError):
            validate_iana_timezone("Invalid/Timezone_Name_123")

    def test_dst_spring_forward_skipped_time(self) -> None:
        """On spring forward (e.g. 02:00 -> 03:00 jump), a 02:30 target is safely caught up."""
        tz = ZoneInfo("America/New_York")
        # 2026-03-08 is US Spring Forward: clocks jump from 01:59:59 to 03:00:00
        # If check runs at 03:05 local time on a scheduled Sunday for a 02:30 target
        local_now = datetime(2026, 3, 8, 3, 5, tzinfo=tz)
        prefs = SimpleNamespace(
            timezone="America/New_York",
            digest_mode=True,
            digest_days=["sun"],
            digest_time_local="02:30",
            digest_last_sent_at=None,
            is_paused=False,
            is_unsubscribed=False,
        )
        # Should be evaluated as due without crashing or missing the scheduled window
        self.assertTrue(is_digest_due(prefs, now_local=local_now))

    def test_dst_fall_back_ambiguous_time_no_duplicate(self) -> None:
        """On fall back (e.g. 01:00 -> 01:59 occurs twice), user receives only 1 digest today."""
        tz = ZoneInfo("America/New_York")
        # 2026-11-01 is US Fall Back: 01:30 happens twice.
        # First send happens at 01:30 (fold=0)
        first_send = datetime(2026, 11, 1, 1, 30, fold=0, tzinfo=tz)
        prefs = SimpleNamespace(
            timezone="America/New_York",
            digest_mode=True,
            digest_days=["sun"],
            digest_time_local="01:30",
            digest_last_sent_at=first_send,
            is_paused=False,
            is_unsubscribed=False,
        )
        # Second occurrence at 01:30 (fold=1)
        second_occurrence = datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=tz)
        # MUST return False because today's digest was already dispatched!
        self.assertFalse(is_digest_due(prefs, now_local=second_occurrence))

    def test_quiet_hours_overnight_and_daytime(self) -> None:
        # Overnight quiet hours: 22:00 to 08:00
        start = time(22, 0)
        end = time(8, 0)
        self.assertTrue(is_in_quiet_hours(time(23, 30), start, end))
        self.assertTrue(is_in_quiet_hours(time(1, 15), start, end))
        self.assertTrue(is_in_quiet_hours(time(7, 59), start, end))
        self.assertFalse(is_in_quiet_hours(time(14, 0), start, end))

        # Daytime quiet hours: 13:00 to 14:00
        d_start = time(13, 0)
        d_end = time(14, 0)
        self.assertTrue(is_in_quiet_hours(time(13, 30), d_start, d_end))
        self.assertFalse(is_in_quiet_hours(time(15, 0), d_start, d_end))

    # ---------------------------------------------------------------------
    # 2. Duplicate Scheduler Execution & Restart Idempotency
    # ---------------------------------------------------------------------
    async def test_no_duplicate_digest_on_worker_restart_or_retries(self) -> None:
        session = AsyncMock()
        service = DigestService(session)

        user = User(id="usr-test-1", email="test@example.com", is_active=True, is_verified=True)
        prefs = UserPreferences(
            user_id="usr-test-1",
            timezone="UTC",
            digest_days=["mon", "tue", "wed", "thu", "fri"],
            digest_time_local="09:00",
            digest_mode=True,
            is_paused=False,
            is_unsubscribed=False,
            skills=["python"],
        )

        # First run: enqueue outbox
        outbox_svc = OutboxService(session)
        dedup_key = "digest:usr-test-1:2026-11-21:email"

        # Mock outbox query: initially not found
        first_query = MagicMock()
        first_query.scalar_one_or_none.return_value = None
        session.execute.return_value = first_query

        rec1, is_new1 = await outbox_svc.enqueue(
            dedup_key=dedup_key,
            recipient="test@example.com",
            channel="email",
            title="Digest 1",
            body="Body 1",
            user_id="usr-test-1",
        )
        self.assertTrue(is_new1)
        self.assertEqual(rec1.dedup_key, dedup_key)

        # Second run (simulating worker restart / Celery retry / duplicate beat task):
        second_query = MagicMock()
        rec1.status = "delivered"
        second_query.scalar_one_or_none.return_value = rec1
        session.execute.return_value = second_query

        rec2, is_new2 = await outbox_svc.enqueue(
            dedup_key=dedup_key,
            recipient="test@example.com",
            channel="email",
            title="Digest 1",
            body="Body 1",
            user_id="usr-test-1",
        )
        # Must return existing record and NOT create a new send
        self.assertFalse(is_new2)
        self.assertEqual(rec2.id, rec1.id)

    # ---------------------------------------------------------------------
    # 3. Bounded Retries & Dead Letter Queue
    # ---------------------------------------------------------------------
    async def test_bounded_retries_and_dead_letter_queue(self) -> None:
        session = AsyncMock()
        outbox_svc = OutboxService(session)

        record = NotificationOutbox(
            id=10,
            dedup_key="test:retry:deadletter",
            recipient="down@provider.com",
            channel="email",
            title="Test",
            body="Body",
            status="pending",
            attempts=2,  # already attempted 2 times
            max_retries=3,
        )

        # Mock delivery failure from adapter
        mock_result = MagicMock()
        mock_result.delivered = False
        mock_result.error = "Connection reset by peer"

        with patch.object(
            outbox_svc.dispatcher._channel_adapters[NotificationChannel.EMAIL],
            "send",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            res = await outbox_svc.deliver_record(record)
            self.assertFalse(res.delivered)
            # Reached max_retries (3), must move to dead_letter!
            self.assertEqual(record.status, "dead_letter")
            self.assertEqual(record.attempts, 3)
            self.assertIn("Connection reset", record.last_error or "")

    # ---------------------------------------------------------------------
    # 4. Unsubscribed and Paused Users
    # ---------------------------------------------------------------------
    def test_unsubscribed_and_paused_users_suppressed(self) -> None:
        tz = ZoneInfo("UTC")
        local_now = datetime(2026, 11, 23, 9, 0, tzinfo=tz)  # Monday 09:00

        # Unsubscribed user
        unsub_prefs = SimpleNamespace(
            timezone="UTC",
            digest_mode=True,
            digest_days=["mon"],
            digest_time_local="09:00",
            digest_last_sent_at=None,
            is_paused=False,
            is_unsubscribed=True,
        )
        self.assertFalse(is_digest_due(unsub_prefs, now_local=local_now))

        # Paused user
        paused_prefs = SimpleNamespace(
            timezone="UTC",
            digest_mode=True,
            digest_days=["mon"],
            digest_time_local="09:00",
            digest_last_sent_at=None,
            is_paused=True,
            is_unsubscribed=False,
        )
        self.assertFalse(is_digest_due(paused_prefs, now_local=local_now))

    # ---------------------------------------------------------------------
    # 5. Stale / Expired Listing Suppression
    # ---------------------------------------------------------------------
    async def test_expired_and_stale_listings_excluded_from_digest(self) -> None:
        session = AsyncMock()
        selector = DigestSelector(session)

        user = User(id="usr-1", email="u@test.com", plan="pro")
        prefs = UserPreferences(
            user_id="usr-1",
            skills=["python"],
            match_threshold=0.3,
            max_per_digest=5,
        )

        active_job = JobRecord(
            id=1,
            title="Senior Python Backend",
            source_name="remoteok",
            source_id="1",
            canonical_id="can-1",
            url="https://remoteok.com/1",
            is_expired=False,
            inventory_state="active",
        )
        expired_job = JobRecord(
            id=2,
            title="Senior Python Engineer",
            source_name="remoteok",
            source_id="2",
            canonical_id="can-2",
            url="https://remoteok.com/2",
            is_expired=True,
            inventory_state="expired",
        )

        mock_repo = MagicMock()
        mock_repo.list_match_candidates = AsyncMock(return_value=[active_job, expired_job])

        with patch("backend.application.services.digest_service.SQLAlchemyJobRepository", return_value=mock_repo):
            # Mock empty user lead actions and sent jobs
            empty_res = MagicMock()
            empty_res.scalars.return_value.all.return_value = []
            session.execute.return_value = empty_res

            leads = await selector.select_digest_leads(user, prefs)
            selected_ids = [l.get("job_id") or l.get("id") for l in leads]
            # Expired job MUST NOT be in selected leads!
            self.assertIn(1, selected_ids)
            self.assertNotIn(2, selected_ids)

    # ---------------------------------------------------------------------
    # 6. Source Outage Resilience
    # ---------------------------------------------------------------------
    async def test_source_outage_does_not_crash_digest(self) -> None:
        session = AsyncMock()
        selector = DigestSelector(session)

        user = User(id="usr-2", email="u2@test.com", plan="free")
        prefs = UserPreferences(
            user_id="usr-2",
            skills=["react"],
            match_threshold=0.3,
            max_per_digest=5,
        )

        # Scrapers had outage; database candidate query returns empty list
        mock_repo = MagicMock()
        mock_repo.list_match_candidates = AsyncMock(return_value=[])

        with patch("backend.application.services.digest_service.SQLAlchemyJobRepository", return_value=mock_repo):
            leads = await selector.select_digest_leads(user, prefs)
            # Should return empty gracefully without throwing
            self.assertEqual(leads, [])

    # ---------------------------------------------------------------------
    # 7. Source Diversity Balancing
    # ---------------------------------------------------------------------
    async def test_source_diversity_balancing(self) -> None:
        session = AsyncMock()
        selector = DigestSelector(session)

        user = User(id="usr-div", email="div@test.com", plan="pro")
        prefs = UserPreferences(
            user_id="usr-div",
            skills=["python"],
            match_threshold=0.2,
            max_per_digest=4,
        )

        # 4 jobs from source A, 2 jobs from source B
        jobs = [
            JobRecord(
                id=i,
                title=f"Senior Python Developer A {i}",
                description="Python FastAPI backend",
                source_name="source_a",
                source_id=str(i),
                canonical_id=f"a-{i}",
                url="#",
                is_expired=False,
                inventory_state="active",
            )
            for i in range(1, 5)
        ] + [
            JobRecord(
                id=i,
                title=f"Lead Python Architect B {i}",
                description="Python cloud system",
                source_name="source_b",
                source_id=str(i),
                canonical_id=f"b-{i}",
                url="#",
                is_expired=False,
                inventory_state="active",
            )
            for i in range(5, 7)
        ]

        mock_repo = MagicMock()
        mock_repo.list_match_candidates = AsyncMock(return_value=jobs)

        with patch("backend.application.services.digest_service.SQLAlchemyJobRepository", return_value=mock_repo):
            empty_res = MagicMock()
            empty_res.scalars.return_value.all.return_value = []
            session.execute.return_value = empty_res

            leads = await selector.select_digest_leads(user, prefs, cap=4)
            sources = [l["source_name"] for l in leads]
            # Ensure both sources are represented (source A cannot monopolize all 4 slots)
            self.assertIn("source_a", sources)
            self.assertIn("source_b", sources)

    # ---------------------------------------------------------------------
    # 8. Provider Observability without Recipient PII
    # ---------------------------------------------------------------------
    async def test_provider_status_observability_no_pii(self) -> None:
        session = AsyncMock()
        outbox_svc = OutboxService(session)

        # Mock status counts
        status_res = MagicMock()
        status_res.all.return_value = [("delivered", 42, 0.0336), ("dead_letter", 1, 0.0008)]

        chan_res = MagicMock()
        chan_res.all.return_value = [("email", "delivered", 42), ("email", "dead_letter", 1)]

        session.execute.side_effect = [status_res, chan_res]

        with patch.dict("os.environ", {"RESEND_API_KEY": "re_secret_key"}, clear=False):
            status = await outbox_svc.get_provider_status()

        # Check structure
        self.assertIn("providers", status)
        self.assertIn("delivery_totals", status)
        self.assertEqual(status["delivery_totals"]["delivered"], 42)
        self.assertEqual(status["delivery_totals"]["dead_letter"], 1)

        # Check provider configuration
        self.assertEqual(status["providers"]["email_resend"]["status"], "operational")

        # Crucial: verify NO recipient PII is leaked in status payload
        status_str = str(status)
        self.assertNotIn("@", status_str)
        self.assertNotIn("re_secret_key", status_str)

    # ---------------------------------------------------------------------
    # 9. Provider Downtime & Honesty (Never Fake Success)
    # ---------------------------------------------------------------------
    def test_unconfigured_provider_honesty(self) -> None:
        service = NotificationService()
        payload = NotificationPayload(
            user_id="usr-1",
            title="Test",
            body="Body",
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            destinations={"email": "u@test.com"},
        )

        with patch.dict("os.environ", {}, clear=True):
            import asyncio
            results = asyncio.run(service.dispatch(payload))

        # Providers not configured must explicitly fail with provider_not_configured
        self.assertEqual(len(results), 2)
        self.assertTrue(all(not r.delivered for r in results))
        self.assertTrue(all(r.error == "provider_not_configured" for r in results))

    # ---------------------------------------------------------------------
    # 10. Immediate Alerts with Caps & Quiet Hours
    # ---------------------------------------------------------------------
    async def test_immediate_alerts_respect_threshold_and_caps(self) -> None:
        session = AsyncMock()
        alert_svc = ImmediateAlertService(session)

        user = User(id="usr-alert", email="alert@example.com", is_active=True, is_verified=True, plan="pro")
        prefs = UserPreferences(
            user_id="usr-alert",
            skills=["fastapi", "python"],
            immediate_alerts_enabled=True,
            immediate_alert_threshold=0.8,
            immediate_alert_cap_per_day=1,
            immediate_alerts_sent_today=1,  # Cap already reached!
            immediate_alerts_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            notification_channels=["email"],
        )

        job = JobRecord(
            id=99,
            title="FastAPI Python Expert needed",
            description="High budget FastAPI gig",
            source_name="remoteok",
            url="https://remoteok.com/job/99",
            budget_min=5000,
            budget_max=10000,
            is_expired=False,
        )

        user_query = MagicMock()
        user_query.all.return_value = [(user, prefs)]
        session.execute.return_value = user_query

        dispatched = await alert_svc.evaluate_job_for_alerts(job)
        # Must be suppressed because daily cap of 1 was already reached
        self.assertEqual(dispatched, [])

    # ---------------------------------------------------------------------
    # 11. Timezone Schedule Calculation Preview
    # ---------------------------------------------------------------------
    def test_calculate_next_send_preview(self) -> None:
        prefs = SimpleNamespace(
            timezone="America/New_York",
            digest_days=["mon", "wed", "fri"],
            digest_time_local="10:00",
            digest_mode=True,
            is_paused=False,
            is_unsubscribed=False,
            digest_last_sent_at=None,
        )
        # Tuesday 2026-11-24 12:00:00 UTC = 07:00:00 EST
        utc_now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
        info = calculate_next_send(prefs, now_utc=utc_now)

        self.assertEqual(info["timezone"], "America/New_York")
        self.assertEqual(info["scheduled_time_local"], "10:00")
        self.assertIn("Wednesday", info["scheduled_days"])
        self.assertIn("2026-11-25 10:00:00", info["next_send_local"])

    # ---------------------------------------------------------------------
    # 12. Cross-User Access Prevention (Inbox Security)
    # ---------------------------------------------------------------------
    async def test_cross_user_inbox_access_prevention(self) -> None:
        from fastapi import HTTPException
        from app.api.v1.notifications import mark_notification_read

        session = AsyncMock()
        user_a = User(id="usr-a", email="a@example.com")
        user_b = User(id="usr-b", email="b@example.com")

        # Notification belonging to user_b
        record_b = NotificationRecord(
            id=55,
            public_id="notif-b",
            user_id="usr-b",
            title="Private Lead",
            body="Secret Opportunity",
            channels=["in_app"],
            is_read=False,
        )

        query_res = MagicMock()
        # Query filtering by user_id="usr-a" returns None
        query_res.scalar_one_or_none.return_value = None
        session.execute.return_value = query_res

        # User A attempts to mark User B's notification as read
        with self.assertRaises(HTTPException) as ctx:
            await mark_notification_read(55, session=session, current_user=user_a)

        self.assertEqual(ctx.exception.status_code, 404)

    # ---------------------------------------------------------------------
    # 13. Webhook Bounce & Complaint Reputation Protection
    # ---------------------------------------------------------------------
    async def test_webhook_bounce_unsubscribes_user(self) -> None:
        from app.api.v1.notifications import WebhookPayload, handle_provider_webhook

        session = AsyncMock()
        user = User(id="usr-bounce", email="bad@invalid-domain.com")
        prefs = UserPreferences(user_id="usr-bounce", is_unsubscribed=False)

        user_query = MagicMock()
        user_query.scalar_one_or_none.return_value = user

        pref_query = MagicMock()
        pref_query.scalar_one_or_none.return_value = prefs

        session.execute.side_effect = [user_query, pref_query]

        payload = WebhookPayload(
            event="email.bounced",
            email="bad@invalid-domain.com",
            reason="550 5.1.1 User unknown",
        )

        result = await handle_provider_webhook("resend", payload, session=session)
        self.assertEqual(result["status"], "unsubscribed")
        self.assertTrue(prefs.is_unsubscribed)
        self.assertIsNotNone(prefs.unsubscribed_at)
        self.assertIn("550", prefs.notes or "")

    # ---------------------------------------------------------------------
    # 14. Digest Preview & Verified Test Send Safeguard
    # ---------------------------------------------------------------------
    async def test_unverified_user_cannot_send_test_digest(self) -> None:
        from fastapi import HTTPException
        from app.api.v1.notifications import send_test_digest

        session = AsyncMock()
        unverified_user = User(id="usr-unverified", email="unverified@example.com", is_verified=False)

        with self.assertRaises(HTTPException) as ctx:
            await send_test_digest(session=session, current_user=unverified_user)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("verification required", ctx.exception.detail.lower())


if __name__ == "__main__":
    unittest.main()
