"""Derive soft skill affinity from Save/Skip lead actions."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.job import JobRecord
from database.models.lead_action import UserLeadAction


class MatchFeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def skill_weights(self, user_id: str) -> dict[str, float]:
        """
        Positive weight for skills on saved jobs; negative for skipped.
        Values are clamped to a small range for MatchingService.
        """
        result = await self.session.execute(
            select(UserLeadAction, JobRecord)
            .join(JobRecord, JobRecord.id == UserLeadAction.job_id)
            .where(UserLeadAction.user_id == user_id)
        )
        saved: Counter[str] = Counter()
        skipped: Counter[str] = Counter()
        for action, job in result.all():
            skills = self._job_skills(job)
            bucket = saved if action.status == "save" else skipped
            if action.status not in {"save", "skip"}:
                continue
            for skill in skills:
                bucket[skill] += 1

        weights: dict[str, float] = {}
        for skill, count in saved.items():
            weights[skill] = weights.get(skill, 0.0) + min(0.12, 0.04 * count)
        for skill, count in skipped.items():
            weights[skill] = weights.get(skill, 0.0) - min(0.12, 0.04 * count)
        return {k: v for k, v in weights.items() if abs(v) >= 0.02}

    def _job_skills(self, job: JobRecord) -> list[str]:
        enrichment = job.enrichment or {}
        raw = list(enrichment.get("skills") or []) + list(job.tags or [])
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            skill = str(item).strip().lower()
            if skill and skill not in seen:
                seen.add(skill)
                out.append(skill)
        return out[:20]
