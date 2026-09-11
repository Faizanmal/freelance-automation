from __future__ import annotations

from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobRecord, JobSource
from app.services.listing_presentation import public_job_payload


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
