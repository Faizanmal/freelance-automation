"""Immediate alert service for user-defined high-fit freelance opportunities.

Dispatches instant alerts when an ingested job matches a user's high-fit threshold,
enforcing user-configured daily caps, quiet hours suppression, and plan entitlements.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import filter_channels_for_user
from backend.application.services.digest_scheduler import (
    get_user_zone,
    is_in_quiet_hours,
    parse_local_time,
)
from backend.application.services.matching import MatchingService
from backend.application.services.notification_service import (
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
)
from backend.application.services.outbox_service import OutboxService
from backend.application.services.persistent_notifications import (
    PersistentNotificationService,
)
from database.models.job import JobRecord
from database.models.notification import DigestSentJob, NotificationRecord
from database.models.preference import UserPreferences
from database.models.user import User
from notifications.templates.email_templates import render_immediate_alert_email


class ImmediateAlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def evaluate_job_for_alerts(
        self,
        job: JobRecord,
    ) -> list[dict[str, Any]]:
        """Evaluates a newly ingested or verified job against all active users for immediate alerts."""
        if bool(getattr(job, "is_expired", False)):
            return []

        # Find candidate users who have immediate alerts enabled
        stmt = (
            select(User, UserPreferences)
            .join(UserPreferences, UserPreferences.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.is_verified.is_(True),
                UserPreferences.is_unsubscribed.is_(False),
                UserPreferences.is_paused.is_(False),
                UserPreferences.immediate_alerts_enabled.is_(True),
            )
        )
        res = await self.session.execute(stmt)
        candidates = res.all()

        matching_svc = MatchingService()
        outbox_svc = OutboxService(self.session)
        persistent = PersistentNotificationService(self.session)

        dispatched_alerts: list[dict[str, Any]] = []

        for user, prefs in candidates:
            # 1. Resolve user timezone and local time
            tz = get_user_zone(getattr(prefs, "timezone", None))
            now_local = datetime.now(UTC).astimezone(tz)
            today_str = now_local.strftime("%Y-%m-%d")

            # 2. Quiet Hours check
            if bool(getattr(prefs, "quiet_hours_enabled", False)):
                start_h, start_m = parse_local_time(
                    getattr(prefs, "quiet_hours_start", "22:00")
                )
                end_h, end_m = parse_local_time(
                    getattr(prefs, "quiet_hours_end", "08:00")
                )
                from datetime import time

                if is_in_quiet_hours(
                    now_local.time(),
                    time(start_h, start_m),
                    time(end_h, end_m),
                ):
                    # Suppress alert during user's quiet hours
                    continue

            # 3. Daily Cap enforcement
            sent_today = int(getattr(prefs, "immediate_alerts_sent_today", 0))
            last_date = getattr(prefs, "immediate_alerts_date", None)
            if last_date != today_str:
                sent_today = 0
                prefs.immediate_alerts_sent_today = 0
                prefs.immediate_alerts_date = today_str

            cap = int(getattr(prefs, "immediate_alert_cap_per_day", 5))
            if sent_today >= cap:
                # Daily cap exhausted
                continue

            # 4. Relevance & Threshold check
            match_score = matching_svc.score(job, prefs)
            threshold = float(getattr(prefs, "immediate_alert_threshold", 0.85))
            if match_score < threshold:
                continue

            # 5. Deduplication check
            dedup_key = f"alert:{user.id}:{job.id}"
            existing_sent = await self.session.execute(
                select(DigestSentJob).where(
                    DigestSentJob.user_id == str(user.id),
                    DigestSentJob.job_id == job.id,
                )
            )
            if existing_sent.scalar_one_or_none() is not None:
                continue

            # 6. Plan channel entitlement filtering
            enabled_channels = getattr(prefs, "notification_channels", None) or ["email"]
            allowed_channels = filter_channels_for_user(user, enabled_channels)
            if not allowed_channels:
                continue

            # 7. Render branded email & text notification
            app_url = "http://localhost:3000"
            unsubscribe_url = (
                f"{app_url}/preferences?action=unsubscribe&user_id={user.id}"
            )
            preferences_url = f"{app_url}/preferences?tab=alerts"

            lead_data = {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "source_name": job.source_name,
                "score": match_score,
                "budget_display": (
                    f"${job.budget_min:,.0f} - ${job.budget_max:,.0f}"
                    if job.budget_min and job.budget_max
                    else "Not specified"
                ),
                "why_matched": f"Scored {int(match_score * 100)}% fit against your verified hunt profile",
                "url": job.url,
            }

            text_body, html_body = render_immediate_alert_email(
                user_name=user.full_name or "there",
                lead=lead_data,
                unsubscribe_url=unsubscribe_url,
                preferences_url=preferences_url,
            )

            title = f"High-Fit Freelance Match: {job.title} ({int(match_score * 100)}%)"

            # 8. Record in Transactional Outbox
            recipient = prefs.alert_email or user.email
            record, is_new = await outbox_svc.enqueue(
                dedup_key=dedup_key,
                recipient=recipient,
                channel="email",
                event_type="immediate_alert",
                title=title,
                body=text_body,
                html_body=html_body,
                payload_json=lead_data,
                user_id=str(user.id),
            )

            if not is_new and record.status == "delivered":
                continue

            # 9. Deliver via dispatcher
            channels_enum = [
                NotificationChannel(c)
                for c in allowed_channels
                if c in NotificationChannel._value2member_map_
            ]
            destinations = {
                "email": recipient,
                "slack_webhook_url": getattr(prefs, "slack_webhook_url", None),
                "discord_webhook_url": getattr(prefs, "discord_webhook_url", None),
                "telegram_chat_id": getattr(prefs, "telegram_chat_id", None),
                "whatsapp_to": getattr(prefs, "whatsapp_to", None),
                "custom_webhook_url": getattr(prefs, "custom_webhook_url", None),
            }

            envelope = NotificationPayload(
                user_id=str(user.id),
                title=title,
                body=text_body,
                channels=channels_enum,
                priority=NotificationPriority.HIGH,
                digest=False,
                destinations=destinations,
                metadata={"job_id": job.id, "match_score": match_score},
            )

            outcomes = await persistent.send(envelope, job_id=job.id)

            # Record success and bump cap
            prefs.immediate_alerts_sent_today += 1
            self.session.add(
                DigestSentJob(
                    user_id=str(user.id),
                    job_id=job.id,
                    digest_id=dedup_key,
                )
            )

            # In-App inbox entry
            inbox_entry = NotificationRecord(
                public_id=f"alert-inbox-{user.id}-{job.id}",
                user_id=str(user.id),
                title=title,
                body=text_body[:300],
                channels=["in_app"],
                priority="high",
                digest=False,
                status="delivered",
                event_type="immediate_alert",
                group_key=f"job:{job.id}",
                is_read=False,
                job_id=job.id,
                metadata_json=lead_data,
            )
            self.session.add(inbox_entry)

            dispatched_alerts.append(
                {
                    "user_id": str(user.id),
                    "job_id": job.id,
                    "score": match_score,
                    "status": outcomes.get("status"),
                }
            )

        await self.session.commit()
        return dispatched_alerts
