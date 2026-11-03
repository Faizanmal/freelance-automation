"""Build hunter queries from aggregated user Hunt Rules (shared pool)."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from database.models.preference import UserPreferences
from database.models.user import User

_MAX_SKILLS_IN_QUERY = 8


def _normalize_skill(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def skills_from_preferences(prefs: UserPreferences) -> list[str]:
    skills = [
        _normalize_skill(s)
        for s in (getattr(prefs, "skills", None) or [])
        if s and str(s).strip()
    ]
    keywords = [
        _normalize_skill(k)
        for k in (prefs.keywords or [])
        if k and str(k).strip()
    ]
    ordered = skills + keywords if skills else keywords
    seen: set[str] = set()
    out: list[str] = []
    for term in ordered:
        if term and term not in seen:
            seen.add(term)
            out.append(term)
    return out


def compose_freelance_query(skills: list[str], *, base: str | None = None) -> str:
    settings = get_settings()
    fallback = (base or settings.serpapi_freelance_query or "").strip()
    top = [s for s in skills if s][:_MAX_SKILLS_IN_QUERY]
    if not top:
        return fallback
    skill_expr = " OR ".join(top)
    return (
        f'("looking for" OR hiring OR need) (freelancer OR contractor) '
        f"({skill_expr}) -course -tutorial"
    )


def compose_jobs_query(skills: list[str], *, base: str | None = None) -> str:
    settings = get_settings()
    fallback = (base or settings.serpapi_jobs_query or "").strip()
    top = [s for s in skills if s][:_MAX_SKILLS_IN_QUERY]
    if not top:
        return fallback
    skill_expr = " OR ".join(top)
    return f"({skill_expr}) (remote OR contract OR freelance) (developer OR engineer)"


class HuntQueryBuilder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def top_skills(self, *, limit: int = _MAX_SKILLS_IN_QUERY) -> list[str]:
        try:
            result = await self.session.execute(
                select(UserPreferences)
                .join(User, User.id == UserPreferences.user_id)
                .where(User.is_active.is_(True))
            )
            scalars_fn = getattr(result, "scalars", None)
            if callable(scalars_fn):
                res = scalars_fn()
                if hasattr(res, "__await__"):
                    res = await res
                all_fn = getattr(res, "all", None)
                if callable(all_fn):
                    items = all_fn()
                    if hasattr(items, "__await__"):
                        items = await items
                else:
                    items = []
            else:
                items = []

            counts: Counter[str] = Counter()
            for prefs in items:
                for skill in skills_from_preferences(prefs):
                    counts[skill] += 1
            return [skill for skill, _ in counts.most_common(limit)]
        except Exception:
            return []

    async def queries_for_sources(
        self, sources: list[str], *, explicit: str | None = None
    ) -> dict[str, str | None]:
        """
        Per-source query map. Explicit user/API query wins for all.
        Otherwise skill-aggregated queries for V1 Serp modes; others None (adapter default).
        """
        if explicit and explicit.strip():
            q = explicit.strip()
            return {source: q for source in sources}

        skills = await self.top_skills()
        freelance_q = compose_freelance_query(skills)
        jobs_q = compose_jobs_query(skills)
        companies_q = jobs_q  # company/ATS hunt benefits from the same skill signal
        mapping: dict[str, str | None] = {}
        for source in sources:
            if source == "serpapi_freelance":
                mapping[source] = freelance_q
            elif source in {"serpapi_jobs", "serpapi_companies"}:
                mapping[source] = companies_q if source == "serpapi_companies" else jobs_q
            else:
                mapping[source] = None
        return mapping
