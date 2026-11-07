"""User show-clock email digests (independent of the hunt/scrape clock)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import (
    clamp_digest_limit,
    destinations_from_preferences,
)
from backend.application.services.lead_findings import LeadFindingsService
from backend.application.services.match_feedback import MatchFeedbackService
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
    now_utc: datetime | None = None,
    window_minutes: int = 20,
) -> bool:
    """True when local clock is on a digest day near digest_time_local and not already sent today."""
    if not bool(getattr(prefs, "digest_mode", True)):
        return False

    if now_local is not None:
        local_now = now_local
    elif now_utc is not None:
        try:
            tz = ZoneInfo((getattr(prefs, "timezone", None) or "UTC").strip() or "UTC")
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")
        local_now = now_utc.astimezone(tz)
    else:
        local_now = _user_now(getattr(prefs, "timezone", None))

    days = _parse_digest_days(getattr(prefs, "digest_days", None))
    if local_now.weekday() not in days:
        return False

    hour, minute = _parse_local_time(getattr(prefs, "digest_time_local", None))
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = abs((local_now - target).total_seconds())
    if delta > window_minutes * 60:
        return False

    last = getattr(prefs, "digest_last_sent_at", None) or getattr(prefs, "last_digest_at", None)
    if last is not None:
        try:
            tz = local_now.tzinfo or ZoneInfo("UTC")
            last_dt = (
                last.astimezone(tz)
                if last.tzinfo
                else last.replace(tzinfo=UTC).astimezone(tz)
            )
            if (
                last_dt.year == local_now.year
                and last_dt.month == local_now.month
                and last_dt.day == local_now.day
            ):
                return False
        except (ValueError, TypeError):
            pass
    return True


class DigestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_due_digests(
        self, *, now_local: datetime | None = None
    ) -> dict[str, int]:
        stmt = (
            select(User, UserPreferences)
            .join(UserPreferences, UserPreferences.user_id == User.id)
            .where(User.is_active.is_(True), User.is_verified.is_(True))
        )
        res = await self.session.execute(stmt)
        pairs = res.all()

        checked = 0
        sent = 0
        skipped = 0

        for user, prefs in pairs:
            checked += 1
            if not is_digest_due(prefs, now_local=now_local):
                skipped += 1
                continue

            delivered = await self._send_user_digest(user, prefs)
            if delivered:
                sent += 1
                prefs.last_digest_at = datetime.now(UTC)
                self.session.add(prefs)
            else:
                skipped += 1

        if sent:
            await self.session.commit()

        return {"checked": checked, "sent": sent, "skipped": skipped}

    async def _send_user_digest(
        self, user: User, prefs: UserPreferences
    ) -> bool:
        cap = clamp_digest_limit(user, getattr(prefs, "max_per_digest", 5))
        repo = SQLAlchemyJobRepository(self.session)
        jobs = await repo.list_recent(limit=300)
        feedback_service = MatchFeedbackService(self.session)
        skill_weights = await feedback_service.skill_weights(str(user.id))

        actions_res = await self.session.execute(
            select(UserLeadAction).where(UserLeadAction.user_id == str(user.id))
        )
        lead_actions = {row.job_id: row.status for row in actions_res.scalars().all()}
        handled_ids = {
            jid for jid, st in lead_actions.items() if st in {"skip", "save", "saved", "pitched", "won"}
        }

        freelance_focus = bool(getattr(prefs, "freelance_focus", True))
        findings = LeadFindingsService().build(
            jobs,
            prefs,
            limit=cap * 2,
            freelance_focus=freelance_focus,
            lead_actions=lead_actions,
            skill_weights=skill_weights,
        )

        leads: list[dict] = []
        for item in findings.get("items", []):
            jid = item.get("job_id") or item.get("id")
            if jid in handled_ids:
                continue
            leads.append(item)
            if len(leads) >= cap:
                break

        if not leads:
            return False

        lead_lines = []
        for idx, lead in enumerate(leads, start=1):
            title = lead.get("title", "Untitled")
            company = lead.get("company") or "Unknown"
            url = lead.get("apply_url") or lead.get("url") or "#"
            score = int((lead.get("score") or 0) * 100)
            lead_lines.append(
                f"{idx}. {title} ({company}) — Match {score}%\n   View: {url}"
            )

        body = (
            f"Here are your top {len(leads)} freelance discovery leads for today:\n\n"
            + "\n\n".join(lead_lines)
            + "\n\nSet your preferences anytime in your Signal Desk account."
        )

        notifier = PersistentNotificationService(self.session)
        destinations = destinations_from_preferences(prefs)
        destinations["email"] = prefs.alert_email or user.email

        outcomes = await notifier.send(
            NotificationPayload(
                user_id=str(user.id),
                title=f"Your Signal Desk Digest — {len(leads)} New Leads",
                body=body,
                channels=[NotificationChannel.EMAIL],
                priority=NotificationPriority.NORMAL,
                digest=True,
                destinations=destinations,
            )
        )
        return int(outcomes.get("delivered_count") or 0) > 0
