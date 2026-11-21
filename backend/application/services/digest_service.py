"""User show-clock digests (independent of the hunt/scrape clock).

Implements reliable scheduled digests, intelligent candidate selection,
deduplication across previous sends, source diversity balancing, stale job suppression,
reputation-preserving email templates, and transactional outbox recording.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import (
    clamp_digest_limit,
    destinations_from_preferences,
    is_pro,
)
from backend.application.services.digest_scheduler import (
    calculate_next_send,
    get_user_zone,
    is_digest_due,
    parse_digest_days,
    parse_local_time,
)
from backend.application.services.lead_findings import LeadFindingsService
from backend.application.services.match_feedback import MatchFeedbackService
from backend.application.services.notification_service import (
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
)
from backend.application.services.outbox_service import OutboxService
from backend.application.services.persistent_notifications import (
    PersistentNotificationService,
)
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.models.job import JobRecord
from database.models.lead_action import UserLeadAction
from database.models.notification import DigestSentJob, NotificationRecord
from database.models.preference import UserPreferences
from database.models.user import User
from notifications.templates.email_templates import (
    render_digest_email,
    render_empty_digest_email,
)


def _format_budget_display(job: Any) -> str:
    """Accurately formats budget without inventing counts or currency numbers."""
    b_min = getattr(job, "budget_min", None)
    b_max = getattr(job, "budget_max", None)
    curr = getattr(job, "compensation_currency", None) or "$"
    period = getattr(job, "compensation_period", None) or ""

    if b_min and b_max:
        if b_min == b_max:
            return f"{curr}{b_min:,.0f} {period}".strip()
        return f"{curr}{b_min:,.0f} - {curr}{b_max:,.0f} {period}".strip()
    if b_min:
        return f"From {curr}{b_min:,.0f} {period}".strip()
    if b_max:
        return f"Up to {curr}{b_max:,.0f} {period}".strip()
    return "Not specified"


def _build_concise_why_matched(lead: dict[str, Any], prefs: UserPreferences) -> str:
    """Builds a concise, honest explanation of why this job was selected."""
    skills = [s.lower() for s in (prefs.skills or []) if str(s).strip()]
    lead_skills = [s.lower() for s in (lead.get("tags") or []) if str(s).strip()]
    matched = set(skills).intersection(set(lead_skills))
    score = int(float(lead.get("score") or lead.get("match_score") or 0.8) * 100)

    if matched:
        matched_str = ", ".join(sorted(matched)[:3])
        return f"Matched skills: {matched_str} • Fit: {score}%"

    keywords = [k.lower() for k in (prefs.keywords or []) if str(k).strip()]
    title = str(lead.get("title") or "").lower()
    matched_kws = [k for k in keywords if k in title]
    if matched_kws:
        return f"Matched keyword: {matched_kws[0]} • Fit: {score}%"

    return f"Profile criteria match • Fit: {score}%"


class DigestSelector:
    """Pulls candidate jobs from the already ingested pool, filtering for freshness, fit,

    deduplication against past digests, stale listing suppression, and source diversity.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def select_digest_leads(
        self,
        user: User,
        prefs: UserPreferences,
        *,
        cap: int | None = None,
    ) -> list[dict[str, Any]]:
        target_cap = cap or clamp_digest_limit(user, getattr(prefs, "max_per_digest", 5))
        repo = SQLAlchemyJobRepository(self.session)

        # 1. Fetch raw candidates matching basic rules from the database
        jobs = await repo.list_match_candidates(
            skills=list(getattr(prefs, "skills", None) or []),
            keywords=list(prefs.keywords or []),
            exclude_keywords=list(prefs.exclude_keywords or []),
            sources=list(prefs.sources or []),
            min_budget=prefs.min_budget,
            max_budget=prefs.max_budget,
            min_hourly_rate=getattr(prefs, "min_hourly_rate", None),
            limit=250,
        )

        # 2. Suppress stale and expired listings before evaluation
        active_jobs = [
            j
            for j in jobs
            if not bool(getattr(j, "is_expired", False))
            and getattr(j, "inventory_state", "active") != "expired"
        ]

        if not active_jobs:
            return []

        # 3. Exclude user's manual lead actions (saved, skipped, won, pitched)
        actions_res = await self.session.execute(
            select(UserLeadAction).where(UserLeadAction.user_id == str(user.id))
        )
        lead_actions = {row.job_id: row.status for row in actions_res.scalars().all()}
        action_suppressed = {
            jid
            for jid, st in lead_actions.items()
            if st in {"skip", "save", "saved", "pitched", "won"}
        }

        # 4. Exclude jobs already delivered in previous digests to this user
        sent_jobs_res = await self.session.execute(
            select(DigestSentJob.job_id).where(DigestSentJob.user_id == str(user.id))
        )
        previously_sent = set(sent_jobs_res.scalars().all())

        # 5. Build ranked findings using LeadFindingsService
        feedback_service = MatchFeedbackService(self.session)
        learning_enabled = await feedback_service.has_ranking_consent(str(user.id))
        skill_weights = await feedback_service.skill_weights(str(user.id))
        freelance_focus = bool(getattr(prefs, "freelance_focus", True))

        findings = LeadFindingsService().build(
            active_jobs,
            prefs,
            limit=target_cap * 3,
            freelance_focus=freelance_focus,
            lead_actions=lead_actions,
            skill_weights=skill_weights,
            learning_enabled=learning_enabled,
        )

        # 6. Apply relevance threshold and deduplication
        threshold = float(getattr(prefs, "match_threshold", 0.35))
        eligible_candidates: list[dict[str, Any]] = []

        for item in findings.get("items", []):
            jid = item.get("job_id") or item.get("id")
            if jid in action_suppressed or jid in previously_sent:
                continue

            score = float(item.get("score") or 0.0)
            if score < threshold:
                continue

            # Format fields
            item["why_matched"] = _build_concise_why_matched(item, prefs)
            item["budget_display"] = item.get("budget_display") or _format_budget_display(
                type("JobDummy", (), item)()
            )
            item["source_name"] = item.get("source_name") or item.get("source") or "Marketplace"
            eligible_candidates.append(item)

        if not eligible_candidates:
            return []

        # 7. Source Diversity Balancing:
        # Don't let a single source monopolize the digest when multiple sources exist
        source_counts: dict[str, int] = {}
        for c in eligible_candidates:
            src = c.get("source_name", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1

        selected: list[dict[str, Any]] = []
        max_per_source = (
            math.ceil(target_cap / 2) if len(source_counts) > 1 and target_cap > 2 else target_cap
        )
        chosen_per_source: dict[str, int] = {}

        for cand in eligible_candidates:
            if len(selected) >= target_cap:
                break
            src = cand.get("source_name", "unknown")
            if chosen_per_source.get(src, 0) < max_per_source:
                selected.append(cand)
                chosen_per_source[src] = chosen_per_source.get(src, 0) + 1

        # Fill remaining slots if cap not reached due to source limitation
        if len(selected) < target_cap:
            selected_ids = {c.get("job_id") or c.get("id") for c in selected}
            for cand in eligible_candidates:
                if len(selected) >= target_cap:
                    break
                jid = cand.get("job_id") or cand.get("id")
                if jid not in selected_ids:
                    selected.append(cand)
                    selected_ids.add(jid)

        return selected


class DigestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.selector = DigestSelector(session)

    async def process_due_digests(
        self, *, now_local: datetime | None = None
    ) -> dict[str, int]:
        """Scans active, verified users and dispatches digests strictly on their local schedule."""
        stmt = (
            select(User, UserPreferences)
            .join(UserPreferences, UserPreferences.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.is_verified.is_(True),
                UserPreferences.is_unsubscribed.is_(False),
                UserPreferences.is_paused.is_(False),
            )
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
                prefs.digest_last_sent_at = datetime.now(UTC)
                self.session.add(prefs)
            else:
                skipped += 1

        if sent:
            await self.session.commit()

        return {"checked": checked, "sent": sent, "skipped": skipped}

    async def _send_user_digest(
        self,
        user: User,
        prefs: UserPreferences,
    ) -> bool:
        """Builds, enqueues, and dispatches an idempotent digest for one user."""
        tz = get_user_zone(getattr(prefs, "timezone", None))
        local_now = datetime.now(UTC).astimezone(tz)
        local_date_str = local_now.strftime("%Y-%m-%d")

        # 1. Select eligible leads
        leads = await self.selector.select_digest_leads(user, prefs)

        # 2. Check Empty Digest Policy
        empty_policy = getattr(prefs, "empty_digest_policy", "suppress")
        if not leads:
            if empty_policy != "send_empty_notification":
                return False

        # 3. Construct Outbox Idempotency Key: f"digest:{user.id}:{local_date_str}:email"
        dedup_key = f"digest:{user.id}:{local_date_str}:email"

        # URLs for template
        app_url = "http://localhost:3000"
        unsubscribe_url = f"{app_url}/preferences?action=unsubscribe&user_id={user.id}"
        preferences_url = f"{app_url}/preferences?tab=alerts"

        if leads:
            text_body, html_body = render_digest_email(
                user_name=user.full_name or "there",
                leads=leads,
                unsubscribe_url=unsubscribe_url,
                preferences_url=preferences_url,
                date_str=local_date_str,
            )
            title = f"Your Signal Desk Digest — {len(leads)} New Leads ({local_date_str})"
        else:
            text_body, html_body = render_empty_digest_email(
                user_name=user.full_name or "there",
                unsubscribe_url=unsubscribe_url,
                preferences_url=preferences_url,
                date_str=local_date_str,
            )
            title = f"Your Signal Desk Digest Update — ({local_date_str})"

        recipient = prefs.alert_email or user.email

        # 4. Enqueue into Transactional Outbox (Guarantees no duplicate send on restart/retries)
        outbox_svc = OutboxService(self.session)
        record, is_new = await outbox_svc.enqueue(
            dedup_key=dedup_key,
            recipient=recipient,
            channel="email",
            event_type="digest",
            title=title,
            body=text_body,
            html_body=html_body,
            payload_json={
                "lead_count": len(leads),
                "job_ids": [l.get("job_id") or l.get("id") for l in leads],
                "date": local_date_str,
            },
            user_id=str(user.id),
        )

        if not is_new and record.status == "delivered":
            # Already delivered!
            return False

        # 5. Deliver through dispatcher
        notifier = PersistentNotificationService(self.session)
        destinations = destinations_from_preferences(prefs)
        destinations["email"] = recipient

        outcomes = await notifier.send(
            NotificationPayload(
                user_id=str(user.id),
                title=title,
                body=text_body,
                channels=[NotificationChannel.EMAIL],
                priority=NotificationPriority.NORMAL,
                digest=True,
                destinations=destinations,
                metadata={"outbox_id": record.id, "lead_count": len(leads)},
            )
        )
        delivered_count = int(outcomes.get("delivered_count") or 0)
        success = delivered_count > 0

        # Update outbox record status
        if success:
            record.status = "delivered"
            record.delivered_at = datetime.now(UTC)
            # Record sent job entries so they are not included in subsequent digests
            for lead in leads:
                jid = lead.get("job_id") or lead.get("id")
                if jid:
                    self.session.add(
                        DigestSentJob(
                            user_id=str(user.id),
                            job_id=int(jid),
                            digest_id=str(outcomes.get("public_id") or dedup_key),
                        )
                    )
        else:
            record.status = "failed"
            record.last_error = "dispatcher_failed"

        # Also mirror in-app inbox entry if enabled or default
        inbox_entry = NotificationRecord(
            public_id=f"inbox-{record.id}-{datetime.now(UTC).timestamp()}",
            user_id=str(user.id),
            title=title,
            body=text_body[:300] + ("..." if len(text_body) > 300 else ""),
            channels=["in_app"],
            priority="normal",
            digest=True,
            status="delivered",
            event_type="digest",
            group_key=f"digest:{local_date_str}",
            is_read=False,
            metadata_json={
                "lead_count": len(leads),
                "date": local_date_str,
            },
        )
        self.session.add(inbox_entry)
        await self.session.flush()

        return success

    async def preview_digest(
        self,
        user: User,
        prefs: UserPreferences,
    ) -> dict[str, Any]:
        """Previews the exact digest from actual eligible data without dispatching."""
        tz = get_user_zone(getattr(prefs, "timezone", None))
        local_now = datetime.now(UTC).astimezone(tz)
        local_date_str = local_now.strftime("%Y-%m-%d")

        leads = await self.selector.select_digest_leads(user, prefs)
        app_url = "http://localhost:3000"
        unsubscribe_url = f"{app_url}/preferences?action=unsubscribe&user_id={user.id}"
        preferences_url = f"{app_url}/preferences?tab=alerts"

        if leads:
            text_body, html_body = render_digest_email(
                user_name=user.full_name or "there",
                leads=leads,
                unsubscribe_url=unsubscribe_url,
                preferences_url=preferences_url,
                date_str=local_date_str,
            )
            title = f"Your Signal Desk Digest — {len(leads)} New Leads ({local_date_str})"
        else:
            text_body, html_body = render_empty_digest_email(
                user_name=user.full_name or "there",
                unsubscribe_url=unsubscribe_url,
                preferences_url=preferences_url,
                date_str=local_date_str,
            )
            title = f"Your Signal Desk Digest Update — ({local_date_str})"

        schedule_info = calculate_next_send(prefs)

        return {
            "title": title,
            "leads": leads,
            "count": len(leads),
            "text_body": text_body,
            "html_preview": html_body,
            "generated_at": datetime.now(UTC).isoformat(),
            "local_date": local_date_str,
            "schedule": schedule_info,
        }

    async def send_test_digest(
        self,
        user: User,
        prefs: UserPreferences,
    ) -> dict[str, Any]:
        """Dispatches an explicit test digest ONLY to the authenticated verified user."""
        if not user.is_verified:
            raise ValueError("Email verification required before sending test digests.")

        tz = get_user_zone(getattr(prefs, "timezone", None))
        local_date_str = datetime.now(UTC).astimezone(tz).strftime("%Y-%m-%d")

        leads = await self.selector.select_digest_leads(user, prefs)
        app_url = "http://localhost:3000"
        unsubscribe_url = f"{app_url}/preferences?action=unsubscribe&user_id={user.id}"
        preferences_url = f"{app_url}/preferences?tab=alerts"

        title = f"[TEST] Signal Desk Digest Preview — {len(leads)} Leads ({local_date_str})"
        if leads:
            text_body, html_body = render_digest_email(
                user_name=user.full_name or "there",
                leads=leads,
                unsubscribe_url=unsubscribe_url,
                preferences_url=preferences_url,
                date_str=local_date_str,
            )
        else:
            text_body, html_body = render_empty_digest_email(
                user_name=user.full_name or "there",
                unsubscribe_url=unsubscribe_url,
                preferences_url=preferences_url,
                date_str=local_date_str,
            )

        recipient = prefs.alert_email or user.email
        notifier = PersistentNotificationService(self.session)
        destinations = destinations_from_preferences(prefs)
        destinations["email"] = recipient

        result = await notifier.send(
            NotificationPayload(
                user_id=str(user.id),
                title=title,
                body=text_body,
                channels=[NotificationChannel.EMAIL],
                priority=NotificationPriority.NORMAL,
                digest=True,
                destinations=destinations,
                metadata={"test_send": True, "lead_count": len(leads)},
            )
        )
        return {
            "status": result["status"],
            "recipient": recipient,
            "lead_count": len(leads),
            "delivered_count": result.get("delivered_count", 0),
            "sent_at": datetime.now(UTC).isoformat(),
        }
