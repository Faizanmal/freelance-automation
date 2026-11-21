"""Two-stage candidate retrieval: keyword + optional semantic cosine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.application.services.matching import MatchingService
from backend.application.services.ranking.embeddings import EmbeddingIndex
from backend.application.services.ranking.profile import MatchProfile
from database.models.job import JobRecord


@dataclass(slots=True)
class RetrievalResult:
    candidates: list[JobRecord]
    path: str
    keyword_count: int
    semantic_count: int
    metrics: dict[str, Any] = field(default_factory=dict)


class CandidateRetrieval:
    """Combine keyword shortlist with optional embedding cosine shortlist."""

    def __init__(
        self,
        *,
        embedding_index: EmbeddingIndex | None = None,
        matcher: MatchingService | None = None,
    ) -> None:
        self.embedding_index = embedding_index or EmbeddingIndex()
        self.matcher = matcher or MatchingService()

    def retrieve(
        self,
        jobs: list[JobRecord],
        profile: MatchProfile,
        *,
        semantic_enabled: bool = False,
        keyword_limit: int = 200,
        semantic_limit: int = 80,
    ) -> RetrievalResult:
        keyword_hits = self._keyword_candidates(jobs, profile, limit=keyword_limit)
        semantic_hits: list[JobRecord] = []
        metrics: dict[str, Any] = {"semantic_enabled": semantic_enabled}

        if semantic_enabled and (profile.skills or profile.keywords):
            try:
                emb_metrics = self.embedding_index.batch_ensure(jobs)
                metrics.update(self.embedding_index.metrics_dict())
                query = self.embedding_index.profile_vector(
                    profile.skills, profile.keywords
                )
                scored: list[tuple[float, JobRecord]] = []
                for job in jobs:
                    vector = job.embedding_vector
                    if not isinstance(vector, list) or len(vector) != len(query):
                        continue
                    sim = self.embedding_index.cosine(
                        query, [float(x) for x in vector]
                    )
                    if sim >= 0.15:
                        scored.append((sim, job))
                scored.sort(key=lambda item: item[0], reverse=True)
                semantic_hits = [job for _, job in scored[:semantic_limit]]
                metrics["embedding_batch"] = {
                    "latency_ms": emb_metrics.latency_ms,
                    "truncated": emb_metrics.truncated,
                    "estimated_cost_usd": emb_metrics.estimated_cost_usd,
                }
            except Exception as exc:  # noqa: BLE001 — always fall back to keyword
                metrics["fallback"] = "keyword"
                metrics["semantic_error"] = type(exc).__name__
                self.embedding_index.metrics.fallback = "keyword"

        by_id: dict[int, JobRecord] = {}
        for job in keyword_hits:
            if job.id is not None:
                by_id[job.id] = job
        for job in semantic_hits:
            if job.id is not None:
                by_id.setdefault(job.id, job)

        if not by_id:
            # Cold start / empty terms: keep full pool for weighted scorer.
            candidates = list(jobs)
            path = "pool"
        elif semantic_hits and keyword_hits:
            candidates = list(by_id.values())
            path = "hybrid"
        elif semantic_hits:
            candidates = list(by_id.values())
            path = "semantic"
        else:
            candidates = list(by_id.values())
            path = "keyword"

        return RetrievalResult(
            candidates=candidates,
            path=path,
            keyword_count=len(keyword_hits),
            semantic_count=len(semantic_hits),
            metrics=metrics,
        )

    def _keyword_candidates(
        self,
        jobs: list[JobRecord],
        profile: MatchProfile,
        *,
        limit: int,
    ) -> list[JobRecord]:
        terms = list(dict.fromkeys([*profile.skills, *profile.keywords]))
        if not terms:
            return list(jobs)[:limit]

        hits: list[JobRecord] = []
        for job in jobs:
            haystack = self._haystack(job)
            if any(self.matcher._contains_keyword(haystack, term) for term in terms):
                hits.append(job)
                if len(hits) >= limit:
                    break
        return hits

    @staticmethod
    def _haystack(job: JobRecord) -> str:
        return " ".join(
            [
                job.title or "",
                job.description or "",
                job.company or "",
                job.location or "",
                job.source_name or "",
                " ".join(job.tags or []),
                " ".join((job.enrichment or {}).get("skills") or []),
                job.analysis_summary or "",
                job.seniority or "",
            ]
        ).lower()
