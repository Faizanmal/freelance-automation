"""Typed match profile from Hunt Rules — hard vs soft vs unknown."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from database.models.preference import UserPreferences

RequirementKind = Literal["hard", "soft", "unknown"]
SCORE_VERSION_WEIGHTED = "weighted_v1"
SCORE_VERSION_HYBRID = "hybrid_v1"
RANKING_CONSENT_PURPOSE = "ranking_personalization"


@dataclass(slots=True)
class ProfileField:
    """Single preference field with explicit strength and provenance."""

    key: str
    value: Any
    kind: RequirementKind
    source: str
    evidence: str | None = None


@dataclass(slots=True)
class MatchProfile:
    """User-facing match profile. Never infers sensitive traits."""

    user_id: str | None
    skills: list[str]
    keywords: list[str]
    exclude_keywords: list[str]
    experience_level: str
    min_budget: float | None
    max_budget: float | None
    min_hourly_rate: float | None
    sources: list[str]
    location: str | None
    timezone: str | None
    freelance_focus: bool
    hide_agency_leads: bool
    match_threshold: float
    skill_weights: dict[str, float]
    learning_enabled: bool
    cold_start: bool
    hard: list[ProfileField] = field(default_factory=list)
    soft: list[ProfileField] = field(default_factory=list)
    unknowns: list[ProfileField] = field(default_factory=list)
    score_version: str = SCORE_VERSION_WEIGHTED
    retrieval_mode: str = "keyword"

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "skills": list(self.skills),
            "keywords": list(self.keywords),
            "exclude_keywords": list(self.exclude_keywords),
            "experience_level": self.experience_level,
            "min_budget": self.min_budget,
            "max_budget": self.max_budget,
            "min_hourly_rate": self.min_hourly_rate,
            "sources": list(self.sources),
            "location": self.location,
            "timezone": self.timezone,
            "freelance_focus": self.freelance_focus,
            "hide_agency_leads": self.hide_agency_leads,
            "match_threshold": self.match_threshold,
            "skill_weights": dict(self.skill_weights),
            "learning_enabled": self.learning_enabled,
            "cold_start": self.cold_start,
            "hard": [asdict(f) for f in self.hard],
            "soft": [asdict(f) for f in self.soft],
            "unknowns": [asdict(f) for f in self.unknowns],
            "score_version": self.score_version,
            "retrieval_mode": self.retrieval_mode,
            "sensitive_traits_inferred": False,
        }


class MatchProfileBuilder:
    """Build a typed MatchProfile from Hunt Rules + optional consented weights."""

    def build(
        self,
        preferences: UserPreferences,
        *,
        skill_weights: dict[str, float] | None = None,
        learning_enabled: bool = False,
        score_version: str = SCORE_VERSION_WEIGHTED,
        retrieval_mode: str = "keyword",
    ) -> MatchProfile:
        skills = _clean_list(getattr(preferences, "skills", None) or [])
        keywords = _clean_list(preferences.keywords or [])
        excludes = _clean_list(preferences.exclude_keywords or [])
        sources = _clean_list(preferences.sources or [])
        experience = (getattr(preferences, "experience_level", None) or "any").strip().lower()
        if experience not in {"any", "junior", "mid", "senior", "lead"}:
            experience = "any"
        location = (getattr(preferences, "location", None) or "").strip() or None
        timezone = (getattr(preferences, "timezone", None) or "").strip() or None
        threshold = (
            float(preferences.match_threshold)
            if preferences.match_threshold is not None
            else 0.35
        )
        weights = dict(skill_weights or {}) if learning_enabled else {}
        cold_start = not skills and not keywords

        # Cold start: slightly wider threshold so newcomers are not locked out.
        if cold_start and threshold > 0.25:
            effective_threshold = 0.25
        else:
            effective_threshold = threshold

        hard: list[ProfileField] = []
        soft: list[ProfileField] = []
        unknowns: list[ProfileField] = []

        if excludes:
            hard.append(
                ProfileField(
                    key="exclude_keywords",
                    value=excludes,
                    kind="hard",
                    source="hunt_rules",
                    evidence="User exclusions always remove matching listings",
                )
            )
        if sources:
            hard.append(
                ProfileField(
                    key="sources",
                    value=sources,
                    kind="hard",
                    source="hunt_rules",
                    evidence="Only allowlisted sources are eligible",
                )
            )
        if preferences.min_budget is not None or preferences.max_budget is not None:
            hard.append(
                ProfileField(
                    key="project_budget",
                    value={
                        "min": preferences.min_budget,
                        "max": preferences.max_budget,
                    },
                    kind="hard",
                    source="hunt_rules",
                    evidence="Budget filter from Hunt Rules",
                )
            )
        min_hourly = getattr(preferences, "min_hourly_rate", None)
        if min_hourly is not None:
            hard.append(
                ProfileField(
                    key="min_hourly_rate",
                    value=min_hourly,
                    kind="hard",
                    source="hunt_rules",
                    evidence="Minimum hourly rate from Hunt Rules",
                )
            )

        if skills:
            soft.append(
                ProfileField(
                    key="skills",
                    value=skills,
                    kind="soft",
                    source="hunt_rules",
                    evidence="Skill overlap drives primary fit score",
                )
            )
        else:
            unknowns.append(
                ProfileField(
                    key="skills",
                    value=[],
                    kind="unknown",
                    source="cold_start",
                    evidence="No skills configured — starter threshold applied",
                )
            )
        if keywords:
            soft.append(
                ProfileField(
                    key="keywords",
                    value=keywords,
                    kind="soft",
                    source="hunt_rules",
                )
            )
        if experience != "any":
            soft.append(
                ProfileField(
                    key="experience_level",
                    value=experience,
                    kind="soft",
                    source="hunt_rules",
                )
            )
        else:
            unknowns.append(
                ProfileField(
                    key="experience_level",
                    value="any",
                    kind="unknown",
                    source="hunt_rules",
                    evidence="Experience preference not set",
                )
            )
        if location:
            soft.append(
                ProfileField(
                    key="location",
                    value=location,
                    kind="soft",
                    source="hunt_rules",
                    evidence="Location is a soft boost, not a hard filter",
                )
            )
        else:
            unknowns.append(
                ProfileField(
                    key="location",
                    value=None,
                    kind="unknown",
                    source="hunt_rules",
                )
            )
        if timezone:
            soft.append(
                ProfileField(
                    key="timezone",
                    value=timezone,
                    kind="soft",
                    source="hunt_rules",
                )
            )
        else:
            unknowns.append(
                ProfileField(
                    key="timezone",
                    value=None,
                    kind="unknown",
                    source="hunt_rules",
                )
            )
        soft.append(
            ProfileField(
                key="freelance_focus",
                value=bool(getattr(preferences, "freelance_focus", True)),
                kind="soft",
                source="hunt_rules",
            )
        )
        if getattr(preferences, "hide_agency_leads", False):
            soft.append(
                ProfileField(
                    key="hide_agency_leads",
                    value=True,
                    kind="soft",
                    source="hunt_rules",
                    evidence="Agency postings filtered after ranking",
                )
            )
        if weights:
            soft.append(
                ProfileField(
                    key="learned_skill_weights",
                    value=weights,
                    kind="soft",
                    source="ranking_personalization",
                    evidence="Consented Save/Skip affinities",
                )
            )

        return MatchProfile(
            user_id=getattr(preferences, "user_id", None),
            skills=skills,
            keywords=keywords,
            exclude_keywords=excludes,
            experience_level=experience,
            min_budget=preferences.min_budget,
            max_budget=preferences.max_budget,
            min_hourly_rate=min_hourly,
            sources=sources,
            location=location,
            timezone=timezone,
            freelance_focus=bool(getattr(preferences, "freelance_focus", True)),
            hide_agency_leads=bool(getattr(preferences, "hide_agency_leads", False)),
            match_threshold=effective_threshold,
            skill_weights=weights,
            learning_enabled=learning_enabled and bool(weights),
            cold_start=cold_start,
            hard=hard,
            soft=soft,
            unknowns=unknowns,
            score_version=score_version,
            retrieval_mode=retrieval_mode,
        )


def _clean_list(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw).strip().lower()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
