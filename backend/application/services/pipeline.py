"""Phase 08 — Lead pipeline CRM (stages, notes, tasks, reminders, bulk, export)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.crm import (
    PIPELINE_STAGES,
    STAGE_TO_STATUS,
    STATUS_TO_STAGE,
    LeadNote,
    LeadReminder,
    LeadStageEvent,
    LeadTask,
    PipelineUndoEvent,
)
from database.models.job import JobRecord
from database.models.lead_action import UserLeadAction

UNDO_TTL = timedelta(minutes=10)
ACTIVE_STAGES = ("saved", "researching", "ready", "applied", "interview", "negotiating")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stage_for_status(status: str) -> str:
    return STATUS_TO_STAGE.get(status, "saved")


def status_for_stage(stage: str) -> str:
    return STAGE_TO_STATUS.get(stage, "save")


def serialize_lead(
    action: UserLeadAction,
    job: JobRecord | None = None,
    *,
    include_job: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": action.id,
        "job_id": action.job_id,
        "status": action.status,
        "pipeline_stage": getattr(action, "pipeline_stage", None) or stage_for_status(action.status),
        "reason": action.reason,
        "feedback_kind": action.feedback_kind,
        "follow_up_at": action.follow_up_at.isoformat() if action.follow_up_at else None,
        "apply_clicked_at": (
            action.apply_clicked_at.isoformat() if action.apply_clicked_at else None
        ),
        "applied_confirmed_at": (
            action.applied_confirmed_at.isoformat()
            if action.applied_confirmed_at
            else None
        ),
        "tags": list(action.tags or []),
        "employer_name": action.employer_name,
        "contact_name": action.contact_name,
        "contact_email": action.contact_email,
        "contact_url": action.contact_url,
        "contact_notes": action.contact_notes,
        "won_value": action.won_value,
        "lost_reason": action.lost_reason,
        "time_spent_seconds": int(action.time_spent_seconds or 0),
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
        "deleted_at": action.deleted_at.isoformat() if action.deleted_at else None,
    }
    if include_job and job is not None:
        payload["job"] = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "source_name": job.source_name,
            "url": job.url,
            "budget_min": job.budget_min,
            "budget_max": job.budget_max,
            "location": job.location,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        }
    return payload


class PipelineService:
    """Single-user lead pipeline. No bulk outward applications or unsolicited contact."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_lead(
        self,
        *,
        user_id: str,
        job_id: int,
        status: str = "save",
        stage: str | None = None,
        reason: str | None = None,
        feedback_kind: str | None = None,
        source: str = "user",
        write_version: int | None = None,
        force: bool = False,
    ) -> UserLeadAction:
        """Upsert a lead action.

        ``force=True`` is for explicit PUT /leads/{id}/action clicks: always
        apply the intended status and bump ``client_write_version``. Without
        force, a missing/low write_version is ignored so late match-feedback
        / beacons cannot undo a newer Save/Skip/Restore. Client gens reset on
        remount, so force is required for durable UI actions.
        """
        row = await self._get_action(user_id, job_id, include_deleted=True)
        target_stage = stage or stage_for_status(status)
        if target_stage not in PIPELINE_STAGES:
            raise ValueError(f"invalid_stage:{target_stage}")
        # Forced PUT /action: keep the explicit save/skip/pitched/won.
        # Pipeline column moves pass stage=… with default status="save": derive
        # status from the stage so "applied" stays pitched, not save.
        if force:
            resolved_status = status
        elif stage:
            resolved_status = status_for_stage(target_stage)
        else:
            resolved_status = status
        if row is None:
            row = UserLeadAction(
                user_id=user_id,
                job_id=job_id,
                status=resolved_status,
                pipeline_stage=target_stage,
                reason=reason,
                feedback_kind=feedback_kind,
                client_write_version=int(write_version or 1),
            )
            self.session.add(row)
            await self.session.flush()
            await self._record_stage(
                row, from_stage=None, to_stage=target_stage, reason=reason, source=source
            )
            return row

        current_version = int(getattr(row, "client_write_version", 0) or 0)
        effective_version = int(write_version) if write_version is not None else 0
        if force:
            # Explicit user click — always win; keep versions monotonic.
            effective_version = max(effective_version, current_version + 1)
        elif effective_version < current_version:
            return row

        # Soft-deleted (Unsave/Restore): force or a strictly newer write may revive.
        if row.deleted_at is not None:
            if not force and effective_version <= current_version:
                return row
            row.deleted_at = None

        prev = row.pipeline_stage or stage_for_status(row.status)
        row.status = resolved_status
        row.pipeline_stage = target_stage
        if reason is not None:
            row.reason = reason
        if feedback_kind is not None:
            row.feedback_kind = feedback_kind
        row.client_write_version = effective_version
        if prev != target_stage:
            await self._record_stage(
                row, from_stage=prev, to_stage=target_stage, reason=reason, source=source
            )
        return row

    async def sync_from_legacy_status(
        self,
        *,
        user_id: str,
        job_id: int,
        status: str,
        reason: str | None = None,
        feedback_kind: str | None = None,
        write_version: int | None = None,
        force: bool = False,
    ) -> UserLeadAction | None:
        """Keep pipeline_stage aligned when Save/Skip / apply paths mutate status."""
        if status == "clear":
            return await self.clear_lead(
                user_id=user_id,
                job_id=job_id,
                write_version=write_version,
                force=force,
            )

        stage = stage_for_status(status)
        return await self.ensure_lead(
            user_id=user_id,
            job_id=job_id,
            status=status,
            stage=stage,
            reason=reason,
            feedback_kind=feedback_kind,
            source="user" if force else "system",
            write_version=write_version,
            force=force,
        )

    async def patch_reason(
        self,
        *,
        user_id: str,
        job_id: int,
        status: str,
        reason: str | None = None,
        write_version: int | None = None,
    ) -> UserLeadAction | None:
        """Update Why? reason on an active lead only — never undelete after Unsave."""
        row = await self._get_action(user_id, job_id, include_deleted=True)
        if row is None:
            return None
        current_version = int(getattr(row, "client_write_version", 0) or 0)
        effective_version = int(write_version) if write_version is not None else 0
        if effective_version < current_version:
            return row
        if row.deleted_at is not None:
            # Unsave/Undo already won — ignore late Why? chip.
            row.client_write_version = max(current_version, effective_version)
            return row
        if row.status != status:
            return row
        if reason is not None:
            row.reason = reason
        row.client_write_version = max(current_version, effective_version)
        return row

    async def _sibling_job_ids(self, job: JobRecord) -> list[int]:
        """Other job rows that are the same listing.

        Exact URL / title+company equality only — never ilike scans on the
        interactive write path (those delayed commits by seconds–minutes).
        """
        ids: set[int] = set()
        url = (job.url or "").strip()
        if url:
            res = await self.session.execute(
                select(JobRecord.id)
                .where(JobRecord.id != job.id, JobRecord.url == url)
                .limit(10)
            )
            ids.update(int(r) for r in res.scalars().all() if r is not None)
        title = (job.title or "").strip()
        company = (job.company or "").strip()
        if title and company and company.lower() not in {"unknown", "n/a", "na"}:
            res = await self.session.execute(
                select(JobRecord.id)
                .where(
                    JobRecord.id != job.id,
                    JobRecord.title == title,
                    JobRecord.company == company,
                )
                .limit(10)
            )
            ids.update(int(r) for r in res.scalars().all() if r is not None)
        return list(ids)

    async def clear_lead(
        self,
        *,
        user_id: str,
        job_id: int,
        write_version: int | None = None,
        force: bool = False,
    ) -> UserLeadAction | None:
        row = await self._get_action(user_id, job_id, include_deleted=True)
        if row is None:
            return None
        current_version = int(getattr(row, "client_write_version", 0) or 0)
        effective_version = int(write_version) if write_version is not None else 0
        if force:
            effective_version = max(effective_version, current_version + 1)
        elif effective_version < current_version:
            return row
        prev = row.pipeline_stage
        row.deleted_at = _utcnow()
        # Keep prior status for audit; soft-delete is what removes it from counts.
        # (Setting status="skip" made Undo look like a Skip if deleted_at lagged.)
        row.pipeline_stage = "archived"
        row.feedback_kind = "clear"
        row.client_write_version = max(current_version, effective_version)
        await self._record_stage(
            row, from_stage=prev, to_stage="archived", reason="clear", source="user"
        )
        # Twin JobRecords for the same listing (common on 9am.works) must clear too,
        # otherwise Restore snaps back when ranking swaps to the sibling skip row.
        job = await self.session.get(JobRecord, job_id)
        if job is not None:
            for sibling_id in await self._sibling_job_ids(job):
                sibling = await self._get_action(
                    user_id, sibling_id, include_deleted=True
                )
                if sibling is None or sibling.deleted_at is not None:
                    continue
                sibling.deleted_at = _utcnow()
                sibling.pipeline_stage = "archived"
                sibling.feedback_kind = "clear"
                if write_version is not None:
                    sibling.client_write_version = max(
                        int(getattr(sibling, "client_write_version", 0) or 0),
                        int(write_version),
                    )
                self.session.add(sibling)
        return row

    async def set_stage(
        self,
        *,
        user_id: str,
        job_id: int,
        stage: str,
        reason: str | None = None,
        lost_reason: str | None = None,
        won_value: float | None = None,
        confirm_applied: bool = False,
    ) -> UserLeadAction:
        if stage not in PIPELINE_STAGES:
            raise ValueError(f"invalid_stage:{stage}")
        row = await self.ensure_lead(
            user_id=user_id, job_id=job_id, stage=stage, reason=reason, source="user"
        )
        if lost_reason is not None:
            row.lost_reason = lost_reason
        if won_value is not None:
            row.won_value = won_value
        if stage == "applied" and confirm_applied:
            row.applied_confirmed_at = row.applied_confirmed_at or _utcnow()
        return row

    async def mark_apply_click(self, *, user_id: str, job_id: int) -> UserLeadAction:
        """Apply-click is not a confirmed application."""
        row = await self.ensure_lead(
            user_id=user_id,
            job_id=job_id,
            status="save",
            stage="ready",
            feedback_kind="apply_click",
            source="system",
        )
        if row.apply_clicked_at is None:
            row.apply_clicked_at = _utcnow()
        # Do not advance to applied or invent pitched/won.
        if row.pipeline_stage in ("discovered", "saved"):
            prev = row.pipeline_stage
            row.pipeline_stage = "ready"
            row.status = "save"
            await self._record_stage(
                row,
                from_stage=prev,
                to_stage="ready",
                reason="apply_click",
                source="system",
            )
        return row

    async def mark_applied_confirmed(
        self, *, user_id: str, job_id: int
    ) -> UserLeadAction:
        row = await self.ensure_lead(
            user_id=user_id,
            job_id=job_id,
            status="pitched",
            stage="applied",
            feedback_kind="outcome",
            source="system",
        )
        row.applied_confirmed_at = _utcnow()
        return row

    async def update_lead(
        self,
        *,
        user_id: str,
        job_id: int,
        **fields: Any,
    ) -> UserLeadAction:
        row = await self._get_action(user_id, job_id)
        if row is None:
            raise LookupError("lead_not_found")
        allowed = {
            "follow_up_at",
            "tags",
            "employer_name",
            "contact_name",
            "contact_email",
            "contact_url",
            "contact_notes",
            "won_value",
            "lost_reason",
            "time_spent_seconds",
        }
        for key, value in fields.items():
            if key in allowed:
                setattr(row, key, value)
        return row

    async def list_leads(
        self,
        *,
        user_id: str,
        stage: str | None = None,
        stages: list[str] | None = None,
        q: str | None = None,
        tag: str | None = None,
        follow_up_due: bool = False,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        stmt = (
            select(UserLeadAction, JobRecord)
            .outerjoin(JobRecord, UserLeadAction.job_id == JobRecord.id)
            .where(
                UserLeadAction.user_id == user_id,
                UserLeadAction.deleted_at.is_(None),
            )
        )
        if stage:
            stmt = stmt.where(UserLeadAction.pipeline_stage == stage)
        elif stages:
            stmt = stmt.where(UserLeadAction.pipeline_stage.in_(stages))
        elif not include_archived:
            stmt = stmt.where(
                UserLeadAction.pipeline_stage.notin_(("archived", "lost"))
            )
        if follow_up_due:
            stmt = stmt.where(
                UserLeadAction.follow_up_at.is_not(None),
                UserLeadAction.follow_up_at <= _utcnow(),
            )
        if tag:
            # JSON contains — portable enough for SQLite/Postgres via cast compare fallback
            stmt = stmt.where(UserLeadAction.tags.is_not(None))
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    JobRecord.title.ilike(like),
                    JobRecord.company.ilike(like),
                    UserLeadAction.employer_name.ilike(like),
                    UserLeadAction.contact_name.ilike(like),
                )
            )
        stmt = stmt.order_by(
            UserLeadAction.follow_up_at.asc().nullslast(),
            UserLeadAction.updated_at.desc(),
        ).offset(offset).limit(min(limit, 200))

        rows = (await self.session.execute(stmt)).all()
        items = []
        for action, job in rows:
            if tag and tag not in (action.tags or []):
                continue
            items.append(serialize_lead(action, job))
        return {"items": items, "count": len(items), "stages": list(PIPELINE_STAGES)}

    async def board(self, *, user_id: str) -> dict[str, Any]:
        result = await self.list_leads(
            user_id=user_id, include_archived=True, limit=200
        )
        columns: dict[str, list[dict[str, Any]]] = {s: [] for s in PIPELINE_STAGES}
        for item in result["items"]:
            stage = item["pipeline_stage"]
            if stage in columns:
                columns[stage].append(item)
        return {"columns": columns, "stages": list(PIPELINE_STAGES)}

    async def bulk_set_stage(
        self,
        *,
        user_id: str,
        job_ids: list[int],
        stage: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Safe internal bulk only — stage changes, never outward contact."""
        if stage not in PIPELINE_STAGES:
            raise ValueError(f"invalid_stage:{stage}")
        if stage == "applied":
            raise ValueError("bulk_applied_forbidden")
        previous: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        for job_id in job_ids[:50]:
            row = await self._get_action(user_id, job_id)
            if row is None:
                continue
            previous.append(
                {
                    "job_id": job_id,
                    "pipeline_stage": row.pipeline_stage,
                    "status": row.status,
                }
            )
            await self.set_stage(
                user_id=user_id, job_id=job_id, stage=stage, reason=reason
            )
            updated.append({"job_id": job_id, "pipeline_stage": stage})
        undo_id = await self._save_undo(
            user_id=user_id,
            action="bulk_set_stage",
            payload={"previous": previous},
        )
        return {"updated": updated, "undo_id": undo_id}

    async def undo(self, *, user_id: str, undo_id: str) -> dict[str, Any]:
        row = (
            await self.session.execute(
                select(PipelineUndoEvent).where(
                    PipelineUndoEvent.id == undo_id,
                    PipelineUndoEvent.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if row is None or row.consumed_at is not None:
            raise LookupError("undo_not_found")
        if row.expires_at < _utcnow():
            raise LookupError("undo_expired")
        restored = []
        if row.action == "bulk_set_stage":
            for item in row.payload.get("previous", []):
                await self.set_stage(
                    user_id=user_id,
                    job_id=int(item["job_id"]),
                    stage=item["pipeline_stage"],
                    reason="undo",
                )
                restored.append(item)
        row.consumed_at = _utcnow()
        return {"restored": restored}

    async def soft_delete(self, *, user_id: str, job_id: int) -> None:
        row = await self._get_action(user_id, job_id)
        if row is None:
            raise LookupError("lead_not_found")
        prev = row.pipeline_stage
        row.deleted_at = _utcnow()
        row.pipeline_stage = "archived"
        row.status = "skip"
        await self._record_stage(
            row, from_stage=prev, to_stage="archived", reason="delete", source="user"
        )

    async def add_note(
        self,
        *,
        user_id: str,
        job_id: int,
        body: str,
        kind: str = "note",
    ) -> LeadNote:
        action = await self.ensure_lead(user_id=user_id, job_id=job_id)
        note = LeadNote(
            user_id=user_id,
            lead_action_id=action.id,
            job_id=job_id,
            body=body.strip(),
            kind=kind,
        )
        self.session.add(note)
        await self.session.flush()
        return note

    async def list_notes(self, *, user_id: str, job_id: int) -> list[LeadNote]:
        action = await self._get_action(user_id, job_id)
        if action is None:
            return []
        rows = (
            await self.session.execute(
                select(LeadNote)
                .where(
                    LeadNote.user_id == user_id,
                    LeadNote.lead_action_id == action.id,
                    LeadNote.deleted_at.is_(None),
                )
                .order_by(LeadNote.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    async def add_task(
        self,
        *,
        user_id: str,
        job_id: int,
        title: str,
        due_at: datetime | None = None,
    ) -> LeadTask:
        action = await self.ensure_lead(user_id=user_id, job_id=job_id)
        task = LeadTask(
            user_id=user_id,
            lead_action_id=action.id,
            job_id=job_id,
            title=title.strip()[:256],
            due_at=due_at,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def complete_task(
        self, *, user_id: str, task_id: int
    ) -> LeadTask:
        task = (
            await self.session.execute(
                select(LeadTask).where(
                    LeadTask.id == task_id, LeadTask.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if task is None or task.deleted_at is not None:
            raise LookupError("task_not_found")
        task.completed_at = _utcnow()
        return task

    async def add_reminder(
        self,
        *,
        user_id: str,
        job_id: int,
        remind_at: datetime,
        message: str | None = None,
        kind: str = "follow_up",
    ) -> LeadReminder:
        action = await self.ensure_lead(user_id=user_id, job_id=job_id)
        # Deduplicate active reminder at same slot
        existing = (
            await self.session.execute(
                select(LeadReminder).where(
                    LeadReminder.user_id == user_id,
                    LeadReminder.lead_action_id == action.id,
                    LeadReminder.remind_at == remind_at,
                    LeadReminder.kind == kind,
                    LeadReminder.cancelled_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        reminder = LeadReminder(
            user_id=user_id,
            lead_action_id=action.id,
            job_id=job_id,
            remind_at=remind_at,
            message=(message or "")[:512] or None,
            kind=kind,
        )
        self.session.add(reminder)
        if action.follow_up_at is None or remind_at < action.follow_up_at:
            action.follow_up_at = remind_at
        await self.session.flush()
        return reminder

    async def cancel_reminder(self, *, user_id: str, reminder_id: int) -> LeadReminder:
        reminder = (
            await self.session.execute(
                select(LeadReminder).where(
                    LeadReminder.id == reminder_id,
                    LeadReminder.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if reminder is None:
            raise LookupError("reminder_not_found")
        reminder.cancelled_at = _utcnow()
        return reminder

    async def stage_history(
        self, *, user_id: str, job_id: int
    ) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(LeadStageEvent)
                .where(
                    LeadStageEvent.user_id == user_id,
                    LeadStageEvent.job_id == job_id,
                )
                .order_by(LeadStageEvent.created_at.asc())
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "from_stage": r.from_stage,
                "to_stage": r.to_stage,
                "reason": r.reason,
                "source": r.source,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def export_csv(self, *, user_id: str) -> str:
        result = await self.list_leads(
            user_id=user_id, include_archived=True, limit=200
        )
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "job_id",
                "title",
                "company",
                "stage",
                "status",
                "follow_up_at",
                "applied_confirmed_at",
                "apply_clicked_at",
                "won_value",
                "lost_reason",
                "tags",
                "url",
            ],
        )
        writer.writeheader()
        for item in result["items"]:
            job = item.get("job") or {}
            writer.writerow(
                {
                    "job_id": item["job_id"],
                    "title": job.get("title"),
                    "company": job.get("company") or item.get("employer_name"),
                    "stage": item["pipeline_stage"],
                    "status": item["status"],
                    "follow_up_at": item.get("follow_up_at"),
                    "applied_confirmed_at": item.get("applied_confirmed_at"),
                    "apply_clicked_at": item.get("apply_clicked_at"),
                    "won_value": item.get("won_value"),
                    "lost_reason": item.get("lost_reason"),
                    "tags": ",".join(item.get("tags") or []),
                    "url": job.get("url"),
                }
            )
        return buf.getvalue()

    async def export_ics_tasks(self, *, user_id: str) -> str:
        """Calendar export for follow-ups and open tasks (user-controlled)."""
        now = _utcnow()
        leads = await self.list_leads(
            user_id=user_id, include_archived=False, limit=200
        )
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Signal Desk//Pipeline//EN",
        ]
        for item in leads["items"]:
            if not item.get("follow_up_at"):
                continue
            stamp = item["follow_up_at"].replace("-", "").replace(":", "").split(".")[0]
            if stamp.endswith("Z") is False and "T" in stamp:
                stamp = stamp + "Z" if not stamp.endswith("Z") else stamp
            title = (item.get("job") or {}).get("title") or f"Lead {item['job_id']}"
            uid = f"followup-{item['id']}@signaldesk"
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTSTART:{stamp[:15]}Z" if len(stamp) >= 15 else f"DTSTART:{stamp}",
                    f"SUMMARY:Follow up — {title}",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    async def workspace_dashboard(
        self, *, user_id: str, demo: bool = False
    ) -> dict[str, Any]:
        if demo:
            return {
                "demo": True,
                "follow_ups_due": 2,
                "qualified_leads": 5,
                "active_opportunities": 4,
                "stage_counts": {
                    "saved": 3,
                    "researching": 1,
                    "ready": 1,
                    "applied": 2,
                    "interview": 1,
                    "negotiating": 0,
                    "won": 1,
                    "lost": 1,
                },
                "stage_conversion": {
                    "saved_to_applied": 0.4,
                    "applied_to_interview": 0.5,
                    "interview_to_won": 0.5,
                },
                "time_spent_seconds": 7200,
                "won_revenue": 4500.0,
                "notes": "Sample dashboard — not your data.",
            }

        rows = (
            await self.session.execute(
                select(UserLeadAction).where(
                    UserLeadAction.user_id == user_id,
                    UserLeadAction.deleted_at.is_(None),
                )
            )
        ).scalars().all()

        stage_counts = {s: 0 for s in PIPELINE_STAGES}
        follow_ups_due = 0
        time_spent = 0
        won_revenue = 0.0
        now = _utcnow()
        for row in rows:
            stage = row.pipeline_stage or stage_for_status(row.status)
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            time_spent += int(row.time_spent_seconds or 0)
            if stage == "won" and row.won_value:
                won_revenue += float(row.won_value)
            if (
                row.follow_up_at
                and row.follow_up_at <= now
                and stage in ACTIVE_STAGES
            ):
                follow_ups_due += 1

        saved_like = (
            stage_counts.get("saved", 0)
            + stage_counts.get("researching", 0)
            + stage_counts.get("ready", 0)
            + stage_counts.get("applied", 0)
            + stage_counts.get("interview", 0)
            + stage_counts.get("negotiating", 0)
            + stage_counts.get("won", 0)
        )
        applied_like = (
            stage_counts.get("applied", 0)
            + stage_counts.get("interview", 0)
            + stage_counts.get("negotiating", 0)
            + stage_counts.get("won", 0)
        )
        interview_like = (
            stage_counts.get("interview", 0)
            + stage_counts.get("negotiating", 0)
            + stage_counts.get("won", 0)
        )
        won = stage_counts.get("won", 0)

        def _rate(num: int, den: int) -> float:
            return round(num / den, 3) if den > 0 else 0.0

        # Qualified = Ready + Applied only (outreach-ready / submitted).
        qualified = stage_counts.get("ready", 0) + stage_counts.get("applied", 0)
        active = sum(stage_counts.get(s, 0) for s in ACTIVE_STAGES)

        return {
            "demo": False,
            "follow_ups_due": follow_ups_due,
            "qualified_leads": qualified,
            "active_opportunities": active,
            "stage_counts": stage_counts,
            "stage_conversion": {
                "saved_to_applied": _rate(applied_like, max(saved_like, 1)),
                "applied_to_interview": _rate(interview_like, max(applied_like, 1)),
                "interview_to_won": _rate(won, max(interview_like, 1)),
            },
            "time_spent_seconds": time_spent,
            "won_revenue": round(won_revenue, 2),
            "notes": None,
        }

    async def _get_action(
        self,
        user_id: str,
        job_id: int,
        *,
        include_deleted: bool = False,
    ) -> UserLeadAction | None:
        clauses = [
            UserLeadAction.user_id == user_id,
            UserLeadAction.job_id == job_id,
        ]
        if not include_deleted:
            clauses.append(UserLeadAction.deleted_at.is_(None))
        return (
            await self.session.execute(select(UserLeadAction).where(and_(*clauses)))
        ).scalar_one_or_none()

    async def _record_stage(
        self,
        row: UserLeadAction,
        *,
        from_stage: str | None,
        to_stage: str,
        reason: str | None,
        source: str,
    ) -> None:
        self.session.add(
            LeadStageEvent(
                user_id=row.user_id,
                lead_action_id=row.id,
                job_id=row.job_id,
                from_stage=from_stage,
                to_stage=to_stage,
                reason=reason,
                source=source,
            )
        )

    async def _save_undo(
        self, *, user_id: str, action: str, payload: dict[str, Any]
    ) -> str:
        undo_id = str(uuid4())
        self.session.add(
            PipelineUndoEvent(
                id=undo_id,
                user_id=user_id,
                action=action,
                payload=payload,
                expires_at=_utcnow() + UNDO_TTL,
            )
        )
        await self.session.flush()
        return undo_id
