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
        pitched: Counter[str] = Counter()
        skipped: Counter[str] = Counter()
        for action, job in result.all():
            skills = self._job_skills(job)
            if action.status == "save":
                for skill in skills:
                    saved[skill] += 1
            elif action.status in {"pitched", "won"}:
                for skill in skills:
                    pitched[skill] += 1
            elif action.status == "skip":
                for skill in skills:
                    skipped[skill] += 1

        weights: dict[str, float] = {}
        for skill, count in saved.items():
            weights[skill] = weights.get(skill, 0.0) + min(0.12, 0.04 * count)
        for skill, count in pitched.items():
            # Pitched/won jobs are high-intent actions; higher weight ceiling
            weights[skill] = weights.get(skill, 0.0) + min(0.18, 0.06 * count)
        for skill, count in skipped.items():
            weights[skill] = weights.get(skill, 0.0) - min(0.12, 0.04 * count)
        return {k: v for k, v in weights.items() if abs(v) >= 0.02}

    async def get_affinity_profile(self, user_id: str) -> dict[str, object]:
        """Return a structured breakdown of learned user affinities for the UI & diagnostics."""
        result = await self.session.execute(
            select(UserLeadAction, JobRecord)
            .join(JobRecord, JobRecord.id == UserLeadAction.job_id)
            .where(UserLeadAction.user_id == user_id)
        )
        saved: Counter[str] = Counter()
        pitched: Counter[str] = Counter()
        skipped: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()

        for action, job in result.all():
            st = str(action.status).lower()
            action_counts[st] += 1
            skills = self._job_skills(job)
            if st == "save":
                for skill in skills:
                    saved[skill] += 1
            elif st in {"pitched", "won"}:
                for skill in skills:
                    pitched[skill] += 1
            elif st == "skip":
                for skill in skills:
                    skipped[skill] += 1

        weights = await self.skill_weights(user_id)
        positive = [
            {
                "skill": k,
                "weight": round(v, 3),
                "saved_count": saved.get(k, 0),
                "pitched_count": pitched.get(k, 0),
            }
            for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True)
            if v > 0
        ]
        negative = [
            {
                "skill": k,
                "weight": round(v, 3),
                "skipped_count": skipped.get(k, 0),
            }
            for k, v in sorted(weights.items(), key=lambda x: x[1])
            if v < 0
        ]

        total_actions = sum(action_counts.values())
        top_pos = [p["skill"] for p in positive[:3]]
        top_neg = [n["skill"] for n in negative[:3]]

        summary_parts: list[str] = []
        if top_pos:
            summary_parts.append(f"Boosting: {', '.join(top_pos)}")
        if top_neg:
            summary_parts.append(f"Deprioritizing: {', '.join(top_neg)}")
        summary = "; ".join(summary_parts) if summary_parts else "No clear skill affinities learned yet."

        return {
            "total_actions": total_actions,
            "saved_count": action_counts.get("save", 0),
            "pitched_count": action_counts.get("pitched", 0) + action_counts.get("won", 0),
            "skipped_count": action_counts.get("skip", 0),
            "learning_active": total_actions > 0,
            "positive_skills": positive,
            "negative_skills": negative,
            "summary": summary,
        }

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
