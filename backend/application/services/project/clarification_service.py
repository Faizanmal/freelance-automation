"""Phase 14 — Project clarification requests, anti-spam, and public Q&A knowledge base."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.application.services.network.org_service import OrgService
from database.models.project import NativeProject, ProjectClarificationRequest
from database.models.user import User

MAX_QUESTIONS_PER_24H = 3


class ClarificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.org_service = OrgService(session)

    async def submit_question(
        self,
        project_id: str,
        freelancer_id: str,
        question: str,
    ) -> ProjectClarificationRequest:
        question_clean = question.strip()
        if len(question_clean) < 10:
            raise ValueError("Clarification question must be at least 10 characters")

        # Anti-spam: Rate limit questions per freelancer per project within 24 hours
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt_count = select(ProjectClarificationRequest).where(
            ProjectClarificationRequest.project_id == project_id,
            ProjectClarificationRequest.freelancer_id == freelancer_id,
            ProjectClarificationRequest.created_at >= since,
        )
        existing_today = (await self.session.execute(stmt_count)).scalars().all()
        if len(existing_today) >= MAX_QUESTIONS_PER_24H:
            raise ValueError(
                f"Rate limit exceeded: You may submit at most {MAX_QUESTIONS_PER_24H} clarification questions per project per 24 hours to prevent spam."
            )

        # Duplicate check
        for q in existing_today:
            if q.question.strip().lower() == question_clean.lower():
                raise ValueError("Duplicate question: You have already submitted this inquiry.")

        now = datetime.now(timezone.utc)
        req = ProjectClarificationRequest(
            id=str(uuid4()),
            project_id=project_id,
            freelancer_id=freelancer_id,
            question=question_clean[:2000],
            answer=None,
            status="pending",
            is_public=True,
            created_at=now,
        )
        self.session.add(req)
        await self.session.commit()
        return req

    async def answer_question(
        self,
        clarification_id: str,
        client_actor_id: str,
        answer: str,
        is_public: bool = True,
    ) -> ProjectClarificationRequest:
        stmt = (
            select(ProjectClarificationRequest)
            .where(ProjectClarificationRequest.id == clarification_id)
            .options(selectinload(ProjectClarificationRequest.project))
        )
        res = await self.session.execute(stmt)
        req = res.scalar_one_or_none()
        if not req:
            raise ValueError("Clarification request not found")

        # Verify client belongs to project's org
        await self.org_service.verify_user_org_permission(
            org_id=req.project.org_id,
            user_id=client_actor_id,
            required_roles={"owner", "admin", "hiring_manager"},
        )

        now = datetime.now(timezone.utc)
        req.answer = answer.strip()[:4000]
        req.status = "answered"
        req.is_public = is_public
        req.answered_at = now
        await self.session.commit()
        return req

    async def get_project_clarifications(
        self, project_id: str, include_pending: bool = False
    ) -> list[dict[str, Any]]:
        stmt = (
            select(ProjectClarificationRequest)
            .where(ProjectClarificationRequest.project_id == project_id)
            .order_by(ProjectClarificationRequest.created_at.asc())
        )
        if not include_pending:
            stmt = stmt.where(
                ProjectClarificationRequest.status == "answered",
                ProjectClarificationRequest.is_public == True,
            )

        res = await self.session.execute(stmt)
        items = res.scalars().all()

        return [
            {
                "id": i.id,
                "question": i.question,
                "answer": i.answer,
                "status": i.status,
                "is_public": i.is_public,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "answered_at": i.answered_at.isoformat() if i.answered_at else None,
            }
            for i in items
        ]
