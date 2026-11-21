"""Ranking pipeline: retrieve → score with weighted_v1 → explain → diversify."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from backend.application.services.matching import JobMatch, MatchingService
from backend.application.services.ranking.diversity import collapse_duplicates, diversify
from backend.application.services.ranking.embeddings import EmbeddingIndex
from backend.application.services.ranking.explanation import (
    ScoreComponent,
    ScoreExplanation,
    build_why_shown,
    confidence_from_evidence,
)
from backend.application.services.ranking.profile import (
    SCORE_VERSION_HYBRID,
    SCORE_VERSION_WEIGHTED,
    MatchProfile,
    MatchProfileBuilder,
)
from backend.application.services.ranking.retrieval import CandidateRetrieval
from database.models.job import JobRecord
from database.models.preference import UserPreferences

logger = logging.getLogger(__name__)


def resolve_pipeline_mode() -> str:
    raw = (os.getenv("MATCH_PIPELINE") or "weighted_v1").strip().lower()
    if raw in {SCORE_VERSION_HYBRID, "hybrid", "hybrid_v1"}:
        return SCORE_VERSION_HYBRID
    return SCORE_VERSION_WEIGHTED


def resolve_semantic_enabled() -> bool:
    raw = (os.getenv("MATCH_SEMANTIC_RETRIEVAL") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class RankedMatch:
    job: JobRecord
    score: float
    fit_score: float
    matched_keywords: list[str]
    reasons: list[str]
    freshness_score: float
    client_quality_score: float
    red_flags: list[str]
    explanation: ScoreExplanation
    score_version: str
    retrieval_path: str

    def as_job_match(self) -> JobMatch:
        return JobMatch(
            job=self.job,
            score=self.fit_score,
            matched_keywords=list(self.matched_keywords),
            reasons=list(self.reasons),
            freshness_score=self.freshness_score,
            client_quality_score=self.client_quality_score,
            red_flags=list(self.red_flags),
        )


@dataclass
class RankingPipeline:
    """Explainable hybrid ranking with deterministic weighted_v1 fallback."""

    matcher: MatchingService = field(default_factory=MatchingService)
    profile_builder: MatchProfileBuilder = field(default_factory=MatchProfileBuilder)
    retrieval: CandidateRetrieval = field(default_factory=CandidateRetrieval)
    embedding_index: EmbeddingIndex = field(default_factory=EmbeddingIndex)

    def __post_init__(self) -> None:
        self.retrieval = CandidateRetrieval(
            embedding_index=self.embedding_index, matcher=self.matcher
        )

    def build_profile(
        self,
        preferences: UserPreferences,
        *,
        skill_weights: dict[str, float] | None = None,
        learning_enabled: bool = False,
    ) -> MatchProfile:
        mode = resolve_pipeline_mode()
        semantic = resolve_semantic_enabled() and mode == SCORE_VERSION_HYBRID
        return self.profile_builder.build(
            preferences,
            skill_weights=skill_weights,
            learning_enabled=learning_enabled,
            score_version=mode,
            retrieval_mode="hybrid" if semantic else "keyword",
        )

    def rank(
        self,
        jobs: list[JobRecord],
        preferences: UserPreferences,
        *,
        skill_weights: dict[str, float] | None = None,
        learning_enabled: bool = False,
        pipeline_mode: str | None = None,
        semantic_enabled: bool | None = None,
    ) -> list[RankedMatch]:
        mode = pipeline_mode or resolve_pipeline_mode()
        semantic = (
            resolve_semantic_enabled()
            if semantic_enabled is None
            else bool(semantic_enabled)
        )
        if mode != SCORE_VERSION_HYBRID:
            semantic = False

        profile = self.profile_builder.build(
            preferences,
            skill_weights=skill_weights,
            learning_enabled=learning_enabled,
            score_version=mode,
            retrieval_mode="hybrid" if semantic else "keyword",
        )

        # Apply cold-start threshold onto a shallow prefs view without mutating DB.
        effective_prefs = preferences
        if profile.cold_start and (
            preferences.match_threshold is None or preferences.match_threshold > 0.25
        ):
            effective_prefs = _prefs_with_threshold(preferences, 0.25)

        try:
            if mode == SCORE_VERSION_HYBRID:
                return self._rank_hybrid(
                    jobs,
                    effective_prefs,
                    profile,
                    skill_weights=skill_weights if learning_enabled else None,
                    semantic_enabled=semantic,
                )
            return self._rank_weighted(
                jobs,
                effective_prefs,
                profile,
                skill_weights=skill_weights if learning_enabled else None,
                retrieval_path="keyword",
            )
        except Exception:
            logger.exception("ranking_pipeline_failed falling_back=weighted_v1")
            return self._rank_weighted(
                jobs,
                effective_prefs,
                profile,
                skill_weights=skill_weights if learning_enabled else None,
                retrieval_path="keyword_fallback",
                force_version=SCORE_VERSION_WEIGHTED,
            )

    def _rank_hybrid(
        self,
        jobs: list[JobRecord],
        preferences: UserPreferences,
        profile: MatchProfile,
        *,
        skill_weights: dict[str, float] | None,
        semantic_enabled: bool,
    ) -> list[RankedMatch]:
        retrieved = self.retrieval.retrieve(
            jobs, profile, semantic_enabled=semantic_enabled
        )
        ranked = self._rank_weighted(
            retrieved.candidates,
            preferences,
            profile,
            skill_weights=skill_weights,
            retrieval_path=retrieved.path,
            force_version=SCORE_VERSION_HYBRID,
            semantic_boost=semantic_enabled,
        )
        return ranked

    def _rank_weighted(
        self,
        jobs: list[JobRecord],
        preferences: UserPreferences,
        profile: MatchProfile,
        *,
        skill_weights: dict[str, float] | None,
        retrieval_path: str,
        force_version: str | None = None,
        semantic_boost: bool = False,
    ) -> list[RankedMatch]:
        version = force_version or SCORE_VERSION_WEIGHTED
        matches = self.matcher.rank_jobs(
            jobs, preferences, skill_weights=skill_weights
        )
        query_vec = None
        if semantic_boost and (profile.skills or profile.keywords):
            query_vec = self.embedding_index.profile_vector(
                profile.skills, profile.keywords
            )

        terms = list(dict.fromkeys([*profile.skills, *profile.keywords]))
        ranked: list[RankedMatch] = []
        for match in matches:
            fit = float(match.score)
            # Optional tiny semantic delta — never dominates keyword fit; no paid boost.
            if query_vec and isinstance(match.job.embedding_vector, list):
                sim = self.embedding_index.cosine(
                    query_vec, [float(x) for x in match.job.embedding_vector]
                )
                fit = max(0.0, min(1.0, fit + min(0.05, sim * 0.05)))

            explanation = self._explain(
                match,
                profile=profile,
                terms=terms,
                fit_score=round(fit, 3),
                score_version=version,
                retrieval_path=retrieval_path,
            )
            ranked.append(
                RankedMatch(
                    job=match.job,
                    score=round(fit, 3),
                    fit_score=round(fit, 3),
                    matched_keywords=list(match.matched_keywords or []),
                    reasons=list(match.reasons or []),
                    freshness_score=match.freshness_score,
                    client_quality_score=match.client_quality_score,
                    red_flags=list(match.red_flags or []),
                    explanation=explanation,
                    score_version=version,
                    retrieval_path=retrieval_path,
                )
            )

        ranked.sort(key=lambda item: item.fit_score, reverse=True)
        ranked = collapse_duplicates(ranked)
        ranked = diversify(ranked)
        return ranked

    def _explain(
        self,
        match: JobMatch,
        *,
        profile: MatchProfile,
        terms: list[str],
        fit_score: float,
        score_version: str,
        retrieval_path: str,
    ) -> ScoreExplanation:
        matched = list(match.matched_keywords or [])
        missing = [t for t in terms if t not in matched] if terms else []
        mismatches: list[str] = []
        for reason in match.reasons or []:
            if "mismatch" in reason or "vs freelance" in reason or "Depriorit" in reason:
                mismatches.append(reason)
            if "nearby experience" in reason or "experience mismatch" in reason:
                mismatches.append(reason)

        components = [
            ScoreComponent(
                name="keyword_overlap",
                weight=0.54,
                contribution=round(
                    0.54 * (len(matched) / len(terms) if terms else 0.45), 3
                ),
                evidence=(
                    f"matched {len(matched)}/{len(terms)} terms"
                    if terms
                    else "no_skills_configured"
                ),
            ),
            ScoreComponent(
                name="freshness",
                weight=0.16,
                contribution=round(0.16 * match.freshness_score, 3),
                evidence="listing age signal",
            ),
            ScoreComponent(
                name="client_quality",
                weight=0.14,
                contribution=round(0.14 * match.client_quality_score, 3),
                evidence="budget/company enrichment signal",
            ),
        ]

        band = confidence_from_evidence(
            matched=len(matched),
            total_terms=len(terms),
            missing=missing,
            mismatches=mismatches,
            cold_start=profile.cold_start,
        )
        why = build_why_shown(
            matched_keywords=matched,
            reasons=list(match.reasons or []),
            retrieval_path=retrieval_path,
            learning=profile.learning_enabled,
        )
        # Survivors passed these hard gates in MatchingService.score_job.
        passed = [
            "non_opportunity_noise",
            "exclude_keywords",
            "budget",
            "match_threshold",
        ]
        if profile.sources:
            passed.insert(0, "sources")
        if terms:
            passed.append("skill_overlap")

        return ScoreExplanation(
            score_version=score_version,
            fit_score=fit_score,
            components=components,
            matched_keywords=matched,
            missing_qualifications=missing[:12],
            mismatches=list(dict.fromkeys(mismatches))[:8],
            hard_filters_passed=passed,
            hard_filters_failed=[],
            reasons=list(match.reasons or []),
            why_shown=why,
            retrieval_path=retrieval_path,
            confidence_band=band,
            eligibility="eligible",
        )

    def sample_ineligible(
        self,
        jobs: list[JobRecord],
        preferences: UserPreferences,
        *,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        """Explain a few hard-filter rejects for transparency / debugging."""
        out: list[dict[str, object]] = []
        for job in jobs:
            detail = self.matcher.explain_ineligibility(job, preferences)
            if detail is None:
                continue
            out.append(detail)
            if len(out) >= limit:
                break
        return out

    def recommendation_meta(
        self,
        preferences: UserPreferences,
        *,
        learning_enabled: bool = False,
    ) -> dict[str, Any]:
        mode = resolve_pipeline_mode()
        semantic = resolve_semantic_enabled() and mode == SCORE_VERSION_HYBRID
        prefs_updated = getattr(preferences, "updated_at", None)
        return {
            "score_version": mode,
            "retrieval_mode": "hybrid" if semantic else "keyword",
            "semantic_enabled": semantic,
            "learning_enabled": learning_enabled,
            "pgvector": False,
            "pgvector_note": (
                "Deferred: JSON embedding_vector + in-process cosine is sufficient "
                "at current pool size; revisit pgvector when ANN latency dominates."
            ),
            "cache_key_fields": [
                "user_id",
                "prefs_updated_at",
                "score_version",
                "retrieval_mode",
                "limit",
                "offset",
            ],
            "prefs_updated_at": (
                prefs_updated.isoformat() if prefs_updated is not None else None
            ),
            "subscription_affects_organic_rank": False,
        }


def _prefs_with_threshold(
    preferences: UserPreferences, threshold: float
) -> UserPreferences:
    """Return a non-persistent prefs object with an overridden threshold."""
    clone = UserPreferences(
        user_id=getattr(preferences, "user_id", "anon"),
        keywords=list(preferences.keywords or []),
        exclude_keywords=list(preferences.exclude_keywords or []),
        skills=list(getattr(preferences, "skills", None) or []),
        experience_level=getattr(preferences, "experience_level", None),
        min_budget=preferences.min_budget,
        max_budget=preferences.max_budget,
        min_hourly_rate=getattr(preferences, "min_hourly_rate", None),
        sources=list(preferences.sources or []),
        match_threshold=threshold,
        notification_channels=list(preferences.notification_channels or []),
        digest_mode=bool(getattr(preferences, "digest_mode", False)),
        freelance_focus=bool(getattr(preferences, "freelance_focus", True)),
        hide_agency_leads=bool(getattr(preferences, "hide_agency_leads", False)),
        location=getattr(preferences, "location", None),
        timezone=getattr(preferences, "timezone", None),
    )
    return clone
