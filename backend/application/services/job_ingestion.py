from __future__ import annotations

from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.duplicate_detection import (
    DuplicateDetectionService,
    JobCandidate,
)
from backend.application.services.enrichment import EnrichmentService, JobEnrichment
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.models.job import JobRecord, JobSource


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

    async def ingest(
        self,
        candidate: JobCandidate,
        *,
        location: str | None = None,
        tags: list | None = None,
    ) -> dict[str, object]:
        existing = await self.repository.get_by_source(
            candidate.source_name, candidate.source_id
        )
        if existing:
            return {
                "action": "skipped",
                "reason": "already_exists",
                "job_id": existing.id,
            }

        by_url = await self.repository.get_by_url(candidate.url)
        if by_url:
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

        enrichment = await self.enrichment_service.enrich(candidate)
        job = JobRecord(
            source_name=candidate.source_name,
            source_id=candidate.source_id,
            canonical_id=str(uuid4()),
            title=candidate.title,
            description=candidate.description,
            url=candidate.url,
            company=candidate.company,
            location=location or (candidate.metadata or {}).get("location"),
            tags=tags or (candidate.metadata or {}).get("tags"),
            budget_min=candidate.budget_min,
            budget_max=candidate.budget_max,
            posted_at=candidate.posted_at,
            duplicate_confidence=0.0,
            source_count=1,
        )
        self._apply_enrichment(job, enrichment)
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
        return {
            "action": "ingested",
            "confidence": 0.0,
            "job_id": job.id,
            "enrichment_provider": enrichment.provider,
            "skills": enrichment.skills[:8],
        }
