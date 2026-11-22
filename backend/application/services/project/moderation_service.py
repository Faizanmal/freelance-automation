"""Phase 14 — Project moderation queue, human reviewer workflow, and appeal resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.project import (
    NativeProject,
    ProjectModerationQueue,
    ProjectStatusHistory,
)
from database.models.user import User


class ModerationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending_queue(self, limit: int = 50) -> list[dict[str, Any]]:
        stmt = (
            select(ProjectModerationQueue)
            .where(ProjectModerationQueue.status.in_(["pending_review", "under_review", "appealed"]))
            .order_by(ProjectModerationQueue.created_at.desc())
            .limit(limit)
            .options(selectinload(ProjectModerationQueue.project))
        )
        res = await self.session.execute(stmt)
        entries = res.scalars().all()

        return [
            {
                "id": e.id,
                "project_id": e.project_id,
                "project_title": e.project.title if e.project else "Unknown",
                "flagged_by": e.flagged_by,
                "reason_code": e.reason_code,
                "evidence_summary": e.evidence_summary,
                "status": e.status,
                "appeal_details": e.appeal_details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

    async def appeal_flagged_project(
        self,
        project_id: str,
        actor_id: str,
        appeal_details: str,
    ) -> ProjectModerationQueue:
        stmt = (
            select(ProjectModerationQueue)
            .where(
                ProjectModerationQueue.project_id == project_id,
                ProjectModerationQueue.status.in_(["pending_review", "under_review", "rejected"]),
            )
            .order_by(ProjectModerationQueue.created_at.desc())
        )
        res = await self.session.execute(stmt)
        entry = res.scalar_one_or_none()
        if not entry:
            raise ValueError("No active moderation record found for this project")

        now = datetime.now(timezone.utc)
        entry.status = "appealed"
        entry.appeal_details = appeal_details.strip()[:4000]
        entry.appealed_at = now
        await self.session.commit()
        return entry

    async def resolve_moderation_entry(
        self,
        queue_id: str,
        reviewer_id: str,
        decision: str,  # "approved" or "rejected"
        reviewer_notes: str,
    ) -> ProjectModerationQueue:
        stmt = (
            select(ProjectModerationQueue)
            .where(ProjectModerationQueue.id == queue_id)
            .options(selectinload(ProjectModerationQueue.project))
        )
        res = await self.session.execute(stmt)
        entry = res.scalar_one_or_none()
        if not entry:
            raise ValueError("Moderation queue entry not found")

        now = datetime.now(timezone.utc)
        entry.status = "approved" if decision == "approved" else "rejected"
        entry.reviewer_id = reviewer_id
        entry.reviewer_notes = reviewer_notes.strip()[:4000]
        entry.resolved_at = now

        project = entry.project
        if project:
            prev_status = project.status
            if decision == "approved":
                project.status = "approved_open"
                project.review_state = "approved"
                project.flagged_reason = None
            else:
                project.status = "needs_clarification"
                project.review_state = "changes_requested"
                project.flagged_reason = entry.reason_code
            project.updated_at = now

            history = ProjectStatusHistory(
                id=str(uuid4()),
                project_id=project.id,
                from_status=prev_status,
                to_status=project.status,
                action=f"moderation_{decision}",
                actor_id=reviewer_id,
                reason=f"Human moderation decision: {decision}. Notes: {reviewer_notes[:100]}",
                created_at=now,
            )
            self.session.add(history)

        await self.session.commit()
        return entry
