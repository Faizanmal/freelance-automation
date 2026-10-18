"""User show-clock email digests (independent of the hunt/scrape clock)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import destinations_from_preferences
from backend.application.services.lead_findings import LeadFindingsService
from backend.application.services.notification_service import (
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
)
from backend.application.services.persistent_notifications import (
    PersistentNotificationService,
)
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.models.lead_action import UserLeadAction
from database.models.preference import UserPreferences
from database.models.user import User

DAY_ALIASES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def _parse_digest_days(raw: list | None) -> set[int]:
    if not raw:
        return {0, 1, 2, 3, 4}  # weekdays
    days: set[int] = set()
    for item in raw:
        key = str(item).strip().lower()
        if key in DAY_ALIASES:
            days.add(DAY_ALIASES[key])
    return days or {0, 1, 2, 3, 4}


def _parse_local_time(value: str | None) -> tuple[int, int]:
    raw = (value or "09:00").strip()
    try:
        hour_s, minute_s = raw.split(":", 1)
        hour = max(0, min(23, int(hour_s)))
        minute = max(0, min(59, int(minute_s)))
        return hour, minute
    except (TypeError, ValueError):
        return 9, 0


def _user_now(timezone_name: str | None) -> datetime:
    try:
        tz = ZoneInfo((timezone_name or "UTC").strip() or "UTC")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.now(UTC).astimezone(tz)


def is_digest_due(
    prefs: UserPreferences,
    *,
    now_local: datetime | None = None,
    window_minutes: int = 20,
) -> bool:
    """True when local clock is on a digest day near digest_time_local and not already sent today."""
    if not bool(getattr(prefs, "digest_mode", True)):
        return False

    local_now = now_local or _user_now(getattr(prefs, "timezone", None))
    days = _parse_digest_days(getattr(prefs, "digest_days", None))
    if local_now.weekday() not in days:
        return False

    hour, minute = _parse_local_time(getattr(prefs, "digest_time_local", None))
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = abs((local_now - target).total_seconds())
    if delta > window_minutes * 60:
        return False

    last = getattr(prefs, "digest_last_sent_at", None)
    if last is not None:
        last_local = last if last.tzinfo else last.replace(tzinfo=UTC)
        last_local = last_local.astimezone(local_now.tzinfo)
        if last_local.date() == local_now.date():
            return False
    return True


class DigestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_due_digests(self) -> dict[str, int]:
        users_result = await self.session.execute(
            select(User).where(User.is_active.is_(True), User.is_verified.is_(True))
        )
        users = list(users_result.scalars().all())
        sent = 0
        skipped = 0
        for user in users:
            prefs_result = await self.session.execute(
                select(UserPreferences).where(UserPreferences.user_id == user.id)
            )
            prefs = prefs_result.scalar_one_or_none()
            if prefs is None or not is_digest_due(prefs):
                skipped += 1
                continue
            if await self._send_digest_for_user(user, prefs):
                sent += 1
            else:
                skipped += 1
        return {"sent": sent, "skipped": skipped, "checked": len(users)}

    async def _send_digest_for_user(self, user: User, prefs: UserPreferences) -> bool:
        actions = await self.session.execute(
            select(UserLeadAction).where(UserLeadAction.user_id == user.id)
        )
        skipped_ids: set[int] = set()
        saved_ids: set[int] = set()
        for row in actions.scalars().all():
            if row.status == "skip":
                skipped_ids.add(row.job_id)
            elif row.status == "save":
                saved_ids.add(row.job_id)

        repo = SQLAlchemyJobRepository(self.session)
        jobs = await repo.list_recent(limit=300)
        last_sent = getattr(prefs, "digest_last_sent_at", None)
        if last_sent is not None:
            cutoff = last_sent if last_sent.tzinfo else last_sent.replace(tzinfo=UTC)
            jobs = [
                job
                for job in jobs
                if (job.created_at or job.posted_at or cutoff) > cutoff
            ]

        focus = bool(getattr(prefs, "freelance_focus", True))
        limit = int(getattr(prefs, "max_per_digest", None) or 10)
        findings = LeadFindingsService().build(
            jobs,
            prefs,
            limit=limit,
            freelance_focus=focus,
            skip_job_ids=skipped_ids,
            saved_job_ids=saved_ids,
        )
        items = findings.get("items") or []
        if not items:
            prefs.digest_last_sent_at = datetime.now(UTC)
            self.session.add(prefs)
            await self.session.commit()
            return False

        lines = []
        for item in items:
            title = item.get("title") or "Lead"
            url = item.get("apply_url") or item.get("url") or ""
            why = item.get("why") or ""
            lines.append(f"- {title}\n  {why}\n  Open original: {url}")
        body = (
            "Your Signal Desk digest — new fits since last send:\n\n"
            + "\n\n".join(lines)
            + "\n\nPitch on the original page. We never auto-apply."
        )

        notifier = PersistentNotificationService(self.session)
        await notifier.send(
            NotificationPayload(
                user_id=user.id,
                title=f"Digest: {len(items)} new lead{'s' if len(items) != 1 else ''}",
                body=body,
                channels=[NotificationChannel.EMAIL],
                priority=NotificationPriority.NORMAL,
                digest=True,
                destinations=destinations_from_preferences(prefs)
                | {"email": prefs.alert_email or user.email},
                metadata={"digest_count": len(items)},
            )
        )
        prefs.digest_last_sent_at = datetime.now(UTC)
        self.session.add(prefs)
        await self.session.commit()
        return True
