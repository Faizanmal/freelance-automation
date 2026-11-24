from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, and_, desc, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.listing_presentation import public_job_payload
from backend.domain.interfaces import IJobRepository
from backend.domain.models import JobOpportunity
from database.models.job import JobRecord, JobSource


class DomainJobRepository(IJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_domain(self, record: JobRecord) -> JobOpportunity:
        posted_at = None
        if record.posted_at:
            try:
                posted_at = datetime.fromisoformat(
                    str(record.posted_at).replace("Z", "+00:00")
                )
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
                "analysis_summary": record.analysis_summary,
            },
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

    async def find_by_external_id(
        self, source_id: str, external_id: str
    ) -> JobOpportunity | None:
        result = await self.session.execute(
            select(JobRecord).where(
                JobRecord.source_name == source_id, JobRecord.source_id == external_id
            )
        )
        record = result.scalar_one_or_none()
        if record:
            return self._to_domain(record)
        return None

    async def find_pending_for_match(self) -> list[JobOpportunity]:
        # Typically we might filter jobs that haven't been matched yet.
        # For simplicity in this adaptation, return the most recent 100 jobs.
        result = await self.session.execute(
            select(JobRecord).order_by(desc(JobRecord.created_at)).limit(100)
        )
        records = result.scalars().all()
        return [self._to_domain(r) for r in records]


class SQLAlchemyJobRepository:
    MARKETPLACE_PATTERNS = (
        "%freelancer%",
        "%upwork%",
        "%fiverr%",
        "%peopleperhour%",
        "%guru.com%",
        "%truelancer%",
    )
    NON_OPPORTUNITY_URL_PATTERNS = (
        "%/blog/%",
        "%/blogs/%",
        "%/article/%",
        "%/articles/%",
        "%/guide/%",
        "%/guides/%",
        "%/tutorial/%",
        "%/tutorials/%",
        "%/tender/%",
        "%/tenders/%",
        "%/procurement/%",
        "%/rfp/%",
        "%tendersontime.com%",
        "%tendertiger.com%",
        "%biddetail.com%",
        "%globaltenders.com%",
        "%dgmarket.com%",
        "%starterindex.com%",
        "%dailyremote.com%",
        "%remoterocketship.com%",
        "%jobleads.com%",
        "%turing.com%",
        "%toptal.com%",
        "%arc.dev%",
        "%kickstartremote.com%",
        "%joinhandshake.com%",
        "%andrejgajdos.com%",
        "%robinwieruch.de%",
        "%apply.workable.com%",
        "%.teamtailor.com%",
        "%://careers.%",
        "%.careers.%",
        "%://jobs.%",
        "%workingnomads.com%",
        "%opentalent.in%",
        "%justjoin.it%",
        "%wearedevelopers.com%",
        "%4dayweek.io%",
        "%dynamitejobs.com%",
        "%hiddenjobs.dev%",
        "%hiredoor.in%",
        "%reactjobs.io%",
        "%freelance-informatique.fr%",
        "%weekday.works%",
        "%cwjobs.co.uk%",
        "%wuaze.com%",
        "%infinityfreeapp.com%",
        "%000webhostapp.com%",
        "%jobs.makesense.org%",
        "%jobs.natwestgroup.com%",
        "%jobs.appliedmaterials.com%",
        "%codingjobboard.com%",
        "%career.luxoft.com%",
        "%://career.%",
        "%.up.railway.app%",
        "%.railway.app%",
    )
    NON_OPPORTUNITY_TITLE_PATTERNS = (
        "%top 10%",
        "%top 15%",
        "%top 20%",
        "%top 25%",
        "%top 5 %",
        "%best freelance%",
        "%best remote%",
        "%how to become%",
        "%how to hire%",
        "%how to find%",
        "%ultimate guide%",
        "%complete guide%",
        "%boilerplates%",
        "%starter kits%",
        "%starter kit%",
        "%hire me%",
        "%jobs in %",
        "%+ jobs%",
        "%search our job%",
        "%careers & recruitment%",
        "%careers and recruitment%",
        "%tender notice%",
        "%e-tender%",
        "%invitation to tender%",
        "%request for proposal%",
        "%request for quotation%",
        "%public procurement%",
        "%government tender%",
    )

    @classmethod
    def _exclude_marketplace_clause(cls):
        clauses = []
        for pattern in cls.MARKETPLACE_PATTERNS:
            clauses.append(func.coalesce(JobRecord.source_name, "").ilike(pattern))
            clauses.append(func.coalesce(JobRecord.company, "").ilike(pattern))
            clauses.append(func.coalesce(JobRecord.url, "").ilike(pattern))
        for url_pat in cls.NON_OPPORTUNITY_URL_PATTERNS:
            clauses.append(func.coalesce(JobRecord.url, "").ilike(url_pat))
        for title_pat in cls.NON_OPPORTUNITY_TITLE_PATTERNS:
            clauses.append(func.coalesce(JobRecord.title, "").ilike(title_pat))
        return not_(or_(*clauses))
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, job_id: int) -> JobRecord | None:
        result = await self.session.execute(
            select(JobRecord).where(JobRecord.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_source(self, source_name: str, source_id: str) -> JobRecord | None:
        result = await self.session.execute(
            select(JobRecord).where(
                JobRecord.source_name == source_name, JobRecord.source_id == source_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> JobRecord | None:
        result = await self.session.execute(
            select(JobRecord).where(JobRecord.url == url)
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        source: str | None = None,
        search: str | None = None,
        include_expired: bool = False,
    ) -> list[JobRecord]:
        query = (
            select(JobRecord)
            .order_by(desc(JobRecord.created_at))
            .offset(offset)
            .limit(limit)
        )
        if not include_expired:
            query = query.where(JobRecord.is_expired == False)
        if source:
            query = query.where(JobRecord.source_name == source)
        else:
            query = query.where(self._exclude_marketplace_clause())
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

    async def list_jobs_after_id(
        self,
        *,
        after_id: int,
        limit: int = 50,
        source: str | None = None,
        search: str | None = None,
        include_expired: bool = False,
    ) -> list[JobRecord]:
        """Cursor pagination by descending id (exclusive after_id)."""
        query = (
            select(JobRecord)
            .where(JobRecord.id < after_id)
            .order_by(desc(JobRecord.id))
            .limit(limit)
        )
        if not include_expired:
            query = query.where(JobRecord.is_expired == False)
        if source:
            query = query.where(JobRecord.source_name == source)
        else:
            query = query.where(self._exclude_marketplace_clause())
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

    async def count_jobs(
        self,
        *,
        source: str | None = None,
        search: str | None = None,
        include_expired: bool = False,
    ) -> int:
        from sqlalchemy import func

        query = select(func.count()).select_from(JobRecord)
        if not include_expired:
            query = query.where(JobRecord.is_expired == False)
        if source:
            query = query.where(JobRecord.source_name == source)
        else:
            query = query.where(self._exclude_marketplace_clause())
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

    async def list_recent(
        self, limit: int = 200, include_expired: bool = False
    ) -> list[JobRecord]:
        query = (
            select(JobRecord)
            .where(self._exclude_marketplace_clause())
            .order_by(desc(JobRecord.created_at))
            .limit(limit)
        )
        if not include_expired:
            query = query.where(JobRecord.is_expired == False)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_match_candidates(
        self,
        *,
        skills: list[str] | None = None,
        keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        sources: list[str] | None = None,
        min_budget: float | None = None,
        max_budget: float | None = None,
        min_hourly_rate: float | None = None,
        limit: int = 300,
        offset: int = 0,
        include_expired: bool = False,
        recent_fallback_limit: int = 300,
    ) -> list[JobRecord]:
        """SQL-stage shortlist for ranking (ILIKE keyword OR + hard filters).

        Falls back to recent inventory when no skills/keywords are configured
        (cold start / starter search).
        """
        terms = [
            str(t).strip()
            for t in [*(skills or []), *(keywords or [])]
            if t and str(t).strip()
        ]
        # Deduplicate case-insensitively while preserving order.
        seen: set[str] = set()
        clean_terms: list[str] = []
        for term in terms:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                clean_terms.append(term)

        query = select(JobRecord).where(self._exclude_marketplace_clause())
        if not include_expired:
            query = query.where(JobRecord.is_expired == False)

        allowed_sources = [
            s.strip().lower() for s in (sources or []) if s and str(s).strip()
        ]
        if allowed_sources:
            query = query.where(func.lower(JobRecord.source_name).in_(allowed_sources))

        excludes = [
            e.strip().lower()
            for e in (exclude_keywords or [])
            if e and str(e).strip()
        ]
        for exclude in excludes[:40]:
            like = f"%{exclude}%"
            query = query.where(
                not_(
                    or_(
                        func.lower(func.coalesce(JobRecord.title, "")).like(like),
                        func.lower(func.coalesce(JobRecord.description, "")).like(like),
                        func.lower(func.coalesce(JobRecord.company, "")).like(like),
                        func.lower(func.coalesce(JobRecord.source_name, "")).like(like),
                        func.lower(func.coalesce(JobRecord.url, "")).like(like),
                    )
                )
            )

        # Soft SQL budget prefilter — Python ranker still applies period-aware rules.
        if min_budget is not None:
            query = query.where(
                or_(
                    JobRecord.budget_max.is_(None),
                    JobRecord.budget_max >= float(min_budget),
                    and_(
                        JobRecord.budget_max.is_(None),
                        JobRecord.budget_min.is_not(None),
                        JobRecord.budget_min >= float(min_budget),
                    ),
                )
            )
        if max_budget is not None:
            query = query.where(
                or_(
                    JobRecord.budget_min.is_(None),
                    JobRecord.budget_min <= float(max_budget),
                )
            )
        if min_hourly_rate is not None:
            # Keep rows with unknown budget; drop clearly-too-low hourly tops when present.
            query = query.where(
                or_(
                    JobRecord.budget_max.is_(None),
                    JobRecord.budget_max >= float(min_hourly_rate),
                    JobRecord.budget_max >= 200,  # likely fixed-price, keep for period check
                )
            )

        if clean_terms:
            term_clauses = []
            for term in clean_terms[:40]:
                like = f"%{term}%"
                term_clauses.append(
                    or_(
                        JobRecord.title.ilike(like),
                        JobRecord.description.ilike(like),
                        JobRecord.company.ilike(like),
                        JobRecord.location.ilike(like),
                        JobRecord.analysis_summary.ilike(like),
                        JobRecord.seniority.ilike(like),
                        # JSON text search (Postgres + SQLite-compatible cast via cast-as-text
                        # is dialect-sensitive; ILIKE on cast works for both in practice).
                        func.cast(JobRecord.tags, String).ilike(like),
                        func.cast(JobRecord.enrichment, String).ilike(like),
                    )
                )
            query = query.where(or_(*term_clauses))
            query = (
                query.order_by(desc(JobRecord.created_at)).offset(offset).limit(limit)
            )
        else:
            # Cold start: recent pool only.
            query = (
                query.order_by(desc(JobRecord.created_at))
                .offset(offset)
                .limit(min(limit, recent_fallback_limit))
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def mark_expired(
        self, job_id: int, reason: str = "reported"
    ) -> JobRecord | None:
        from datetime import UTC, datetime

        job = await self.get_by_id(job_id)
        if job is None:
            return None
        job.is_expired = True
        job.expired_at = datetime.now(UTC)
        job.expired_reason = reason
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

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

    async def add_source(
        self, job: JobRecord, source_name: str, source_id: str, url: str
    ) -> JobSource:
        source = JobSource(
            job=job, source_name=source_name, source_id=source_id, url=url
        )
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
            "source_count": job.source_count or 1,
            "duplicate_confidence": job.duplicate_confidence,
            "seniority": job.seniority,
            "analysis_summary": job.analysis_summary,
            "enrichment": job.enrichment or {},
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "is_expired": bool(getattr(job, "is_expired", False)),
            "expired_at": job.expired_at.isoformat() if getattr(job, "expired_at", None) else None,
            "expired_reason": getattr(job, "expired_reason", None),
            "work_type": getattr(job, "work_type", None) or "unknown",
            "compensation_period": getattr(job, "compensation_period", None),
            "compensation_currency": getattr(job, "compensation_currency", None),
            "first_seen_at": (
                job.first_seen_at.isoformat()
                if getattr(job, "first_seen_at", None)
                else None
            ),
            "last_seen_at": (
                job.last_seen_at.isoformat()
                if getattr(job, "last_seen_at", None)
                else None
            ),
            "last_checked_at": (
                job.last_checked_at.isoformat()
                if getattr(job, "last_checked_at", None)
                else None
            ),
            "inventory_state": getattr(job, "inventory_state", None) or (
                "expired" if getattr(job, "is_expired", False) else "active"
            ),
        }
        return public_job_payload(raw)
