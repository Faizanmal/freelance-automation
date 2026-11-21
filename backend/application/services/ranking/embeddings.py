"""Content-hash keyed embeddings with budget limits and keyword fallback."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.duplicate_detection import SimpleEmbeddingProvider
from database.models.job import JobRecord

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_VERSION = "local_bow_v1"
EMBEDDING_DIM = 64
DEFAULT_BATCH_LIMIT = 64
DEFAULT_BUDGET_MS = 250


@dataclass(slots=True)
class EmbeddingMetrics:
    model_version: str = EMBEDDING_MODEL_VERSION
    jobs_considered: int = 0
    jobs_embedded: int = 0
    jobs_persisted: int = 0
    cache_hits: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    truncated: bool = False
    fallback: str | None = None
    reindex: bool = False


@dataclass
class EmbeddingIndex:
    """Index over job embedding vectors (JSON column or computed)."""

    provider: SimpleEmbeddingProvider = field(default_factory=SimpleEmbeddingProvider)
    model_version: str = EMBEDDING_MODEL_VERSION
    metrics: EmbeddingMetrics = field(default_factory=EmbeddingMetrics)

    def content_hash(self, text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()[:32]

    def job_text(self, job: JobRecord) -> str:
        enrichment = job.enrichment or {}
        skills = " ".join(str(s) for s in (enrichment.get("skills") or []))
        tags = " ".join(str(t) for t in (job.tags or []))
        return " ".join(
            [
                job.title or "",
                (job.description or "")[:2000],
                job.company or "",
                skills,
                tags,
                job.seniority or "",
            ]
        ).strip()

    def ensure_vector(
        self,
        job: JobRecord,
        *,
        force: bool = False,
    ) -> list[float] | None:
        text = self.job_text(job)
        if not text:
            return None
        digest = self.content_hash(text)
        enrichment = dict(job.enrichment or {})
        meta = dict(enrichment.get("embedding_meta") or {})
        existing = job.embedding_vector
        if (
            not force
            and isinstance(existing, list)
            and len(existing) == EMBEDDING_DIM
            and meta.get("content_hash") == digest
            and meta.get("model_version") == self.model_version
        ):
            self.metrics.cache_hits += 1
            return [float(x) for x in existing]

        vector = self.provider.embed(text)
        job.embedding_vector = vector
        meta.update(
            {
                "content_hash": digest,
                "model_version": self.model_version,
                "dim": EMBEDDING_DIM,
            }
        )
        enrichment["embedding_meta"] = meta
        job.enrichment = enrichment
        self.metrics.jobs_embedded += 1
        return vector

    def batch_ensure(
        self,
        jobs: list[JobRecord],
        *,
        batch_limit: int = DEFAULT_BATCH_LIMIT,
        budget_ms: float = DEFAULT_BUDGET_MS,
        force: bool = False,
    ) -> EmbeddingMetrics:
        started = time.perf_counter()
        self.metrics = EmbeddingMetrics(
            model_version=self.model_version, reindex=force
        )
        self.metrics.jobs_considered = len(jobs)
        dirty: list[JobRecord] = []
        for index, job in enumerate(jobs):
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if index >= batch_limit or elapsed_ms > budget_ms:
                self.metrics.truncated = True
                break
            before = job.embedding_vector
            before_meta = (job.enrichment or {}).get("embedding_meta")
            self.ensure_vector(job, force=force)
            if job.embedding_vector is not before or (
                (job.enrichment or {}).get("embedding_meta") != before_meta
            ):
                dirty.append(job)
        self.metrics.latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        self.metrics.estimated_cost_usd = 0.0
        logger.info(
            "embedding_batch model=%s considered=%s embedded=%s cache_hits=%s "
            "latency_ms=%.1f truncated=%s dirty=%s",
            self.model_version,
            self.metrics.jobs_considered,
            self.metrics.jobs_embedded,
            self.metrics.cache_hits,
            self.metrics.latency_ms,
            self.metrics.truncated,
            len(dirty),
        )
        return self.metrics

    async def persist_dirty(
        self,
        session: AsyncSession,
        jobs: list[JobRecord],
        *,
        batch_limit: int = DEFAULT_BATCH_LIMIT,
        budget_ms: float = DEFAULT_BUDGET_MS,
        force: bool = False,
    ) -> EmbeddingMetrics:
        """Compute missing/stale embeddings and commit them to the DB."""
        metrics = self.batch_ensure(
            jobs, batch_limit=batch_limit, budget_ms=budget_ms, force=force
        )
        persisted = 0
        for job in jobs:
            meta = (job.enrichment or {}).get("embedding_meta") or {}
            if job.embedding_vector and meta.get("model_version") == self.model_version:
                session.add(job)
                persisted += 1
        if persisted:
            await session.commit()
        metrics.jobs_persisted = persisted
        self.metrics = metrics
        logger.info(
            "embedding_persist model=%s persisted=%s latency_ms=%.1f "
            "logged_private_profile_text=false",
            self.model_version,
            persisted,
            metrics.latency_ms,
        )
        return metrics

    def profile_vector(self, skills: list[str], keywords: list[str]) -> list[float]:
        text = " ".join([*skills, *keywords])
        if not text.strip():
            return [0.0] * EMBEDDING_DIM
        return self.provider.embed(text)

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / (na * nb)))

    def metrics_dict(self) -> dict[str, Any]:
        m = self.metrics
        return {
            "model_version": m.model_version,
            "jobs_considered": m.jobs_considered,
            "jobs_embedded": m.jobs_embedded,
            "jobs_persisted": m.jobs_persisted,
            "cache_hits": m.cache_hits,
            "latency_ms": m.latency_ms,
            "estimated_cost_usd": m.estimated_cost_usd,
            "truncated": m.truncated,
            "fallback": m.fallback,
            "reindex": m.reindex,
            # Never log private profile text.
            "logged_private_profile_text": False,
        }
