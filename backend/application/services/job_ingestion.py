from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.duplicate_detection import (
    DuplicateDetectionService,
    JobCandidate,
)
from backend.application.services.enrichment import EnrichmentService, JobEnrichment
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.models.job import JobRecord, JobSource

_SOURCE_ID_MAX = 512


def _fit_source_id(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) <= _SOURCE_ID_MAX:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class JobIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        duplicate_service: DuplicateDetectionService | None = None,
        enrichment_service: EnrichmentService | None = None,
    ) -> None:
        self.session = session
        self.duplicate_service = duplicate_service or DuplicateDetectionService()
        self.enrichment_service = enrichment_service or EnrichmentService()
        self.repository = SQLAlchemyJobRepository(session)

    def _job_to_candidate(self, job: JobRecord) -> JobCandidate:
        return JobCandidate(
            source_name=job.source_name,
            source_id=job.source_id,
            title=job.title,
            description=job.description,
            url=job.url,
            company=job.company,
            budget_min=job.budget_min,
            budget_max=job.budget_max,
            posted_at=job.posted_at,
            metadata={"location": job.location, "tags": job.tags or []},
        )

    def _apply_enrichment(self, job: JobRecord, enrichment: JobEnrichment) -> None:
        job.enrichment = enrichment.to_dict()
        job.seniority = enrichment.seniority
        job.analysis_summary = enrichment.summary
        existing_tags = [str(tag).lower() for tag in (job.tags or [])]
        merged = list(dict.fromkeys([*existing_tags, *enrichment.skills]))
        job.tags = merged[:30]
        if job.budget_min is None and job.budget_max is None:
            b_min = getattr(enrichment, "budget_min", None)
            b_max = getattr(enrichment, "budget_max", None)
            if b_min is not None or b_max is not None:
                job.budget_min = b_min
                job.budget_max = b_max

    async def ingest(
        self,
        candidate: JobCandidate,
        *,
        location: str | None = None,
        tags: list | None = None,
    ) -> dict[str, object]:
        # Google Jobs / board tokens can exceed jobs.source_id VARCHAR(512).
        candidate.source_id = _fit_source_id(candidate.source_id)

        from backend.application.services.page_type import (
            PAGE_TYPE_JOB_POST,
            classify_page_type_llm,
            is_non_opportunity_noise,
        )

        if is_non_opportunity_noise(
            candidate.title, candidate.description, candidate.url, candidate.company
        ):
            return {
                "action": "rejected",
                "reason": "non_opportunity_noise",
            }

        # Dedupe BEFORE any LLM call — scrapes re-see the same URLs constantly and
        # were burning Groq TPM classifying already-indexed rows (429 storms).
        existing = await self.repository.get_by_source(
            candidate.source_name, candidate.source_id
        )
        if existing:
            # Idempotent replay: touch last_seen/checked; never duplicate rows.
            # Never auto-republish removed/expired listings.
            now = datetime.now(UTC)
            if hasattr(existing, "last_checked_at"):
                existing.last_checked_at = now
            if getattr(existing, "is_expired", False) or getattr(
                existing, "inventory_state", None
            ) in {"removed", "expired"}:
                await self.repository.update(existing)
                return {
                    "action": "skipped",
                    "reason": "expired_or_removed",
                    "job_id": existing.id,
                }
            if hasattr(existing, "last_seen_at"):
                existing.last_seen_at = now
            await self.repository.update(existing)
            return {
                "action": "skipped",
                "reason": "already_exists",
                "job_id": existing.id,
            }

        by_url = await self.repository.get_by_url(candidate.url)
        if by_url:
            now = datetime.now(UTC)
            if hasattr(by_url, "last_seen_at"):
                by_url.last_seen_at = now
            await self.repository.add_source(
                by_url, candidate.source_name, candidate.source_id, candidate.url
            )
            return {"action": "linked", "reason": "same_url", "job_id": by_url.id}

        # Fuzzy dedupe only within the same source to avoid cross-board false merges.
        recent = [
            job
            for job in await self.repository.list_recent(limit=150)
            if job.source_name == candidate.source_name
        ]
        for job in recent:
            decision = self.duplicate_service.detect_duplicate(
                self._job_to_candidate(job), candidate
            )
            if decision.is_duplicate:
                merged = self.duplicate_service.merge_duplicate(
                    self._job_to_candidate(job), candidate, decision
                )
                job.title = merged.title or job.title
                job.description = merged.description or job.description
                job.company = merged.company or job.company
                job.budget_min = (
                    merged.budget_min
                    if merged.budget_min is not None
                    else job.budget_min
                )
                job.budget_max = (
                    merged.budget_max
                    if merged.budget_max is not None
                    else job.budget_max
                )
                job.duplicate_confidence = decision.confidence
                await self.repository.add_source(
                    job, candidate.source_name, candidate.source_id, candidate.url
                )
                await self.repository.update(job)
                return {
                    "action": "merged",
                    "confidence": decision.confidence,
                    "reasons": decision.reasons,
                    "job_id": job.id,
                }

        # Optional LLM refine only for net-new candidates.
        llm_type = await classify_page_type_llm(
            candidate.title, candidate.description, candidate.url
        )
        if llm_type and llm_type != PAGE_TYPE_JOB_POST:
            return {
                "action": "rejected",
                "reason": f"non_opportunity_noise:{llm_type}",
            }

        enrichment = await self.enrichment_service.enrich(candidate)
        meta = candidate.metadata or {}
        now = datetime.now(UTC)
        job = JobRecord(
            source_name=candidate.source_name,
            source_id=candidate.source_id,
            canonical_id=str(uuid4()),
            title=candidate.title,
            description=candidate.description,
            url=candidate.url,
            company=candidate.company,
            location=location or meta.get("location"),
            tags=tags or meta.get("tags"),
            budget_min=candidate.budget_min,
            budget_max=candidate.budget_max,
            posted_at=candidate.posted_at,
            duplicate_confidence=0.0,
            source_count=1,
            work_type=meta.get("work_type") or "unknown",
            compensation_period=meta.get("compensation_period") or "unknown",
            compensation_currency=meta.get("compensation_currency"),
            first_seen_at=now,
            last_seen_at=now,
            last_checked_at=now,
            inventory_state="active",
        )
        self._apply_enrichment(job, enrichment)
        # Preserve classification evidence inside enrichment JSON (additive).
        enrich_dict = dict(job.enrichment or {})
        if meta.get("classification_evidence"):
            enrich_dict["classification_evidence"] = meta["classification_evidence"]
        if meta.get("provenance"):
            enrich_dict["provenance"] = meta["provenance"]
        job.enrichment = enrich_dict
        job.sources.append(
            JobSource(
                source_name=candidate.source_name,
                source_id=candidate.source_id,
                url=candidate.url,
            )
        )
        try:
            await self.repository.create(job)
        except IntegrityError:
            await self.session.rollback()
            raced = await self.repository.get_by_source(
                candidate.source_name, candidate.source_id
            )
            if raced:
                return {
                    "action": "skipped",
                    "reason": "race_duplicate",
                    "job_id": raced.id,
                }
            by_url = await self.repository.get_by_url(candidate.url)
            if by_url:
                return {
                    "action": "linked",
                    "reason": "race_same_url",
                    "job_id": by_url.id,
                }
            raise
        except (DBAPIError, SQLAlchemyError) as exc:
            await self.session.rollback()
            return {
                "action": "skipped",
                "reason": f"db_error:{exc.__class__.__name__}",
                "detail": str(exc.orig if isinstance(exc, DBAPIError) else exc)[:300],
            }
        return {
            "action": "ingested",
            "confidence": 0.0,
            "job_id": job.id,
            "enrichment_provider": enrichment.provider,
            "skills": enrichment.skills[:8],
        }
