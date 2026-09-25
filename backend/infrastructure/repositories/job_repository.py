from __future__ import annotations

from typing import Any
from datetime import datetime
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.job import JobRecord, JobSource

from backend.application.services.listing_presentation import public_job_payload
from backend.domain.interfaces import IJobRepository
from backend.domain.models import JobOpportunity

class DomainJobRepository(IJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_domain(self, record: JobRecord) -> JobOpportunity:
        posted_at = None
        if record.posted_at:
            try:
                posted_at = datetime.fromisoformat(str(record.posted_at).replace("Z", "+00:00"))
            except ValueError:
                pass
                
        return JobOpportunity(
            source=record.source_name,
            external_id=record.source_id,
            title=record.title,
            company=record.company or "",
            location=record.location,
            description=record.description,
            url=record.url,
            posted_at=posted_at,
            metadata={
                "tags": record.tags,
                "budget_min": record.budget_min,
                "budget_max": record.budget_max,
                "seniority": record.seniority,
                "enrichment": record.enrichment,
                "analysis_summary": record.analysis_summary
            }
        )

    def _to_record(self, job: JobOpportunity) -> JobRecord:
        # Construct basic JobRecord. Canonical ID might need generating depending on existing logic.
        return JobRecord(
            source_name=job.source,
            source_id=job.external_id,
            canonical_id=f"{job.source}::{job.external_id}",
            title=job.title,
            description=job.description,
            url=job.url,
            company=job.company,
            location=job.location,
            posted_at=job.posted_at.isoformat() if job.posted_at else None,
            tags=job.metadata.get("tags"),
            budget_min=job.metadata.get("budget_min"),
            budget_max=job.metadata.get("budget_max"),
            seniority=job.metadata.get("seniority"),
            enrichment=job.metadata.get("enrichment"),
            analysis_summary=job.metadata.get("analysis_summary"),
        )

    async def save(self, job: JobOpportunity) -> Any:
        record = self._to_record(job)
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def find_by_external_id(self, source_id: str, external_id: str) -> JobOpportunity | None:
        result = await self.session.execute(
            select(JobRecord).where(JobRecord.source_name == source_id, JobRecord.source_id == external_id)
        )
        record = result.scalar_one_or_none()
        if record:
            return self._to_domain(record)
        return None

    async def find_pending_for_match(self) -> list[JobOpportunity]:
        # Typically we might filter jobs that haven't been matched yet. 
        # For simplicity in this adaptation, return the most recent 100 jobs.
        result = await self.session.execute(select(JobRecord).order_by(desc(JobRecord.created_at)).limit(100))
        records = result.scalars().all()
        return [self._to_domain(r) for r in records]

class SQLAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, job_id: int) -> JobRecord | None:
        result = await self.session.execute(select(JobRecord).where(JobRecord.id == job_id))
        return result.scalar_one_or_none()

    async def get_by_source(self, source_name: str, source_id: str) -> JobRecord | None:
        result = await self.session.execute(
            select(JobRecord).where(JobRecord.source_name == source_name, JobRecord.source_id == source_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> JobRecord | None:
        result = await self.session.execute(select(JobRecord).where(JobRecord.url == url))
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        source: str | None = None,
        search: str | None = None,
    ) -> list[JobRecord]:
        query = select(JobRecord).order_by(desc(JobRecord.created_at)).offset(offset).limit(limit)
        if source:
            query = query.where(JobRecord.source_name == source)
        if search:
            like = f"%{search}%"
            query = query.where(
                or_(
                    JobRecord.title.ilike(like),
                    JobRecord.description.ilike(like),
                    JobRecord.company.ilike(like),
                )
            )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_jobs(self, *, source: str | None = None, search: str | None = None) -> int:
        from sqlalchemy import func

        query = select(func.count()).select_from(JobRecord)
        if source:
            query = query.where(JobRecord.source_name == source)
        if search:
            like = f"%{search}%"
            query = query.where(
                or_(
                    JobRecord.title.ilike(like),
                    JobRecord.description.ilike(like),
                    JobRecord.company.ilike(like),
                )
            )
        result = await self.session.execute(query)
        return int(result.scalar_one())

    async def list_recent(self, limit: int = 200) -> list[JobRecord]:
        result = await self.session.execute(select(JobRecord).order_by(desc(JobRecord.created_at)).limit(limit))
        return list(result.scalars().all())

    async def create(self, job: JobRecord) -> JobRecord:
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def update(self, job: JobRecord) -> JobRecord:
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def add_source(self, job: JobRecord, source_name: str, source_id: str, url: str) -> JobSource:
        source = JobSource(job=job, source_name=source_name, source_id=source_id, url=url)
        job.source_count = (job.source_count or 1) + 1
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def to_candidate_dict(self, job: JobRecord) -> dict[str, Any]:
        raw = {
            "id": job.id,
            "source_name": job.source_name,
            "source_id": job.source_id,
            "canonical_id": job.canonical_id,
            "title": job.title,
            "description": job.description,
            "url": job.url,
            "company": job.company,
            "location": job.location,
            "tags": job.tags or [],
            "budget_min": job.budget_min,
            "budget_max": job.budget_max,
            "posted_at": job.posted_at,
            "source_count": job.source_count,
            "duplicate_confidence": job.duplicate_confidence,
            "seniority": job.seniority,
            "analysis_summary": job.analysis_summary,
            "enrichment": job.enrichment or {},
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        return public_job_payload(raw)

