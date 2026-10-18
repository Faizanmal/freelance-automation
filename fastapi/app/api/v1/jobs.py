from __future__ import annotations

from typing import Annotated

from app.api.dependencies import rate_limit_api
from app.core.logging.logger import get_logger
from app.ingestion.sources import COMMERCIAL_FREE_SOURCES, COMMERCIAL_PRO_SOURCES
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.apply_service import ApplyError, ApplyService
from backend.application.services.billing import (
    blocked_restricted_sources,
    filter_sources_for_user,
    limits_for_user,
)
from backend.application.services.duplicate_detection import (
    DuplicateDetectionService,
    JobCandidate,
)
from backend.application.services.job_ingestion import JobIngestionService
from backend.application.services.proposal_draft import ProposalDraftService
from backend.application.services.scrape_service import ScrapeService
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.core.session import get_db
from database.models.preference import UserPreferences
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/jobs", tags=["jobs"])
duplicate_service = DuplicateDetectionService()
logger = get_logger(__name__)


class JobIngestionRequest(BaseModel):
    source_name: str
    source_id: str
    title: str
    description: str
    url: str
    company: str | None = None
    location: str | None = None
    tags: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    posted_at: str | None = None


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    confidence: float
    reasons: list[str]
    matched_job_id: int | None = None


class ScrapeRequest(BaseModel):
    sources: list[str] = Field(default_factory=lambda: list(COMMERCIAL_FREE_SOURCES))
    limit: int = Field(default=40, ge=1, le=100)
    notify_matches: bool = False
    query: str | None = None
    # Default sync so the UI always gets scrape stats. Queue only when workers are up.
    background: bool = False


class ApplyFormFields(BaseModel):
    proposal: str = Field(min_length=1)
    bid_amount: float | None = None
    currency: str = "USD"
    delivery_days: int | None = Field(default=7, ge=1, le=365)
    milestone_plan: str | None = None
    milestone_percentage: int | None = Field(default=100, ge=1, le=100)


class ApplyRequest(BaseModel):
    confirm: bool = False
    form_fields: ApplyFormFields


class JobOut(BaseModel):
    id: int
    source_name: str
    source_id: str
    canonical_id: str
    title: str
    description: str
    url: str
    company: str | None = None
    location: str | None = None
    tags: list = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    posted_at: str | None = None
    source_count: int = 1
    duplicate_confidence: float | None = None
    seniority: str | None = None
    analysis_summary: str | None = None
    enrichment: dict = Field(default_factory=dict)
    created_at: str | None = None
    description_excerpt: str | None = None
    full_description_available: bool = False
    source_attribution: str | None = None
    source_label: str | None = None
    apply_url: str | None = None


import json

from app.core.redis_client import get_redis


@router.get("", response_model=dict)
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    search: str | None = None,
) -> dict:
    redis_client = await get_redis()
    cache_key = f"jobs_cache:{limit}:{offset}:{source or 'all'}:{search or 'none'}"

    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except json.JSONDecodeError as e:
            import logging

            logging.getLogger(__name__).debug("Cache retrieval failed: %s", e)

    repo = SQLAlchemyJobRepository(session)
    jobs = await repo.list_jobs(
        limit=limit, offset=offset, source=source, search=search
    )
    total = await repo.count_jobs(source=source, search=search)

    items = [
        JobOut(**(await repo.to_candidate_dict(job))).model_dump(mode="json")
        for job in jobs
    ]
    result = {
        "total": total,
        "items": items,
    }

    if redis_client:
        try:
            await redis_client.setex(cache_key, 60, json.dumps(result))
        except json.JSONDecodeError as e:
            import logging

            logging.getLogger(__name__).debug("Cache storage failed: %s", e)

    return result


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> JobOut:
    repo = SQLAlchemyJobRepository(session)
    job = await repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut(**(await repo.to_candidate_dict(job)))


@router.post("/ingest")
async def ingest_job(
    payload: JobIngestionRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(rate_limit_api)],
) -> dict[str, object]:
    service = JobIngestionService(session)
    candidate = JobCandidate(
        source_name=payload.source_name,
        source_id=payload.source_id,
        title=payload.title,
        description=payload.description,
        url=payload.url,
        company=payload.company,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
        posted_at=payload.posted_at,
        metadata={"location": payload.location, "tags": payload.tags},
    )
    return await service.ingest(candidate, location=payload.location, tags=payload.tags)


@router.post("/scrape")
async def scrape_jobs(
    payload: ScrapeRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(rate_limit_api)],
) -> dict[str, object]:
    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Verify your email before scraping. Check your inbox or use /auth/resend-verification.",
                "code": "email_verification_required",
                "verify_path": "/auth/verify",
            },
        )
    restricted = blocked_restricted_sources(payload.sources)
    if restricted:
        raise HTTPException(
            status_code=403,
            detail={
                "message": (
                    "These sources are excluded from the commercial product until "
                    "written licensing/permission is secured."
                ),
                "restricted_sources": restricted,
                "allowed_free": list(COMMERCIAL_FREE_SOURCES),
                "allowed_pro": list(COMMERCIAL_PRO_SOURCES),
            },
        )
    limits = limits_for_user(current_user)
    allowed_sources = filter_sources_for_user(current_user, payload.sources)
    blocked = [source for source in payload.sources if source not in allowed_sources]
    if blocked:
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Pro sources require an active Pro plan.",
                "blocked_sources": blocked,
                "upgrade": "/pricing",
            },
        )
    limit = min(payload.limit, limits.scrape_limit)

    import os
    import sys

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    use_background = False
    if payload.background:
        try:
            from workers.availability import celery_workers_online

            use_background = celery_workers_online()
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            logger.warning(
                "Celery availability check failed; using sync scrape: %s", exc
            )
            use_background = False

    if use_background:
        try:
            from workers.jobs.tasks import scrape_jobs_task

            task = scrape_jobs_task.delay(
                sources=allowed_sources,
                limit=limit,
                notify_matches=payload.notify_matches,
                query=payload.query,
            )
            return {
                "status": "queued",
                "task_id": task.id,
                "message": "Scrape queued on a Celery worker.",
                "plan": limits.name,
                "scrape_limit": limits.scrape_limit,
                "total_fetched": 0,
                "total_ingested": 0,
                "total_merged": 0,
                "total_skipped": 0,
                "alerts_sent": 0,
                "sources": {},
            }
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            logger.warning(
                "Celery scrape enqueue failed; falling back to sync: %s", exc
            )

    service = ScrapeService(session)
    summary = await service.run(
        allowed_sources,
        limit=limit,
        notify_matches=payload.notify_matches,
        query=payload.query,
    )
    return {
        "status": "completed",
        "task_id": None,
        "message": "Scrape completed.",
        "plan": limits.name,
        "scrape_limit": limits.scrape_limit,
        **summary,
    }


@router.post("/{job_id}/proposal-draft")
async def proposal_draft(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(rate_limit_api)],
) -> dict[str, object]:
    repo = SQLAlchemyJobRepository(session)
    job = await repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    prefs_result = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = prefs_result.scalar_one_or_none()
    if prefs is None:
        prefs = UserPreferences(
            user_id=current_user.id,
            keywords=["python", "fastapi", "react"],
            exclude_keywords=[],
            sources=[],
            notification_channels=["email"],
            match_threshold=0.35,
            digest_mode=False,
            alert_email=current_user.email,
        )
    return await ProposalDraftService().draft(
        user=current_user, preferences=prefs, job=job
    )


@router.post("/{job_id}/apply")
async def apply_to_job(
    job_id: int,
    payload: ApplyRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(rate_limit_api)],
) -> dict[str, object]:
    repo = SQLAlchemyJobRepository(session)
    job = await repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        result = await ApplyService(session).submit(
            user=current_user,
            job=job,
            form_fields=payload.form_fields.model_dump(),
            confirm=payload.confirm,
        )
        await session.commit()
        return result
    except ApplyError as exc:
        await session.commit()
        status = 400
        if exc.code in {
            "submit_unsupported",
            "email_not_found",
            "email_not_configured",
        }:
            status = 422
        if exc.code in {"upwork_not_configured", "email_not_configured"}:
            status = 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post("/detect-duplicate", response_model=DuplicateCheckResponse)
async def detect_duplicate(
    payload: JobIngestionRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(rate_limit_api)],
) -> DuplicateCheckResponse:
    candidate = JobCandidate(
        source_name=payload.source_name,
        source_id=payload.source_id,
        title=payload.title,
        description=payload.description,
        url=payload.url,
        company=payload.company,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
        posted_at=payload.posted_at,
    )
    repo = SQLAlchemyJobRepository(session)
    recent = await repo.list_recent(limit=150)
    best: DuplicateCheckResponse | None = None
    for job in recent:
        decision = duplicate_service.detect_duplicate(
            JobCandidate(
                source_name=job.source_name,
                source_id=job.source_id,
                title=job.title,
                description=job.description,
                url=job.url,
                company=job.company,
                budget_min=job.budget_min,
                budget_max=job.budget_max,
                posted_at=job.posted_at,
            ),
            candidate,
        )
        if decision.is_duplicate and (
            best is None or decision.confidence > best.confidence
        ):
            best = DuplicateCheckResponse(
                is_duplicate=True,
                confidence=decision.confidence,
                reasons=decision.reasons,
                matched_job_id=job.id,
            )
    if best:
        return best
    return DuplicateCheckResponse(
        is_duplicate=False, confidence=0.0, reasons=["no_match"], matched_job_id=None
    )
