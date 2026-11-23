"""Trust intelligence + listing report APIs (Phase 06)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from app.api.dependencies import get_current_user, require_roles
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.trust.employer_research import (
    research_employer_with_fetch,
)
from backend.application.services.trust.listing_reports import (
    ALLOWED_REASONS,
    ListingReportService,
)
from backend.application.services.trust.service import TrustIntelligenceService
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.core.session import get_db
from database.models.audit import AuditEvent
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/trust", tags=["trust"])


class ListingReportRequest(BaseModel):
    reason_code: Literal[
        "payment_before_work",
        "sensitive_data_request",
        "misleading_or_duplicate",
        "unclear_scope_budget",
        "excessive_unpaid_test",
        "suspicious_link",
        "other_trust_concern",
        "correction_request",
    ]
    details: str | None = Field(default=None, max_length=2000)
    correction_requested: bool = False


class ReportReviewRequest(BaseModel):
    outcome: Literal[
        "confirmed_concern",
        "no_action",
        "corrected",
        "dismissed_abuse",
        "needs_more_info",
    ]
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["resolved", "dismissed", "corrected", "in_review"] = "resolved"

    @model_validator(mode="after")
    def review_requires_reason(self):
        if not self.notes or len(self.notes.strip()) < 10:
            raise ValueError("Moderation review requires a reason of at least 10 characters")
        return self


class CorrectionRequest(BaseModel):
    message: str = Field(min_length=3, max_length=1500)


@router.get("/jobs/{job_id}")
async def job_trust_intelligence(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    include_evidence: bool = Query(True),
) -> dict[str, Any]:
    repo = SQLAlchemyJobRepository(session)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    payload = TrustIntelligenceService().analyze_job(
        job, include_evidence_records=include_evidence
    )
    payload["job_id"] = job_id
    return payload


@router.get("/jobs/{job_id}/employer")
async def job_employer_research(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    fetch: bool = Query(
        False,
        description="If true, SSRF-safe fetch of allowlisted hiring URL",
    ),
) -> dict[str, Any]:
    repo = SQLAlchemyJobRepository(session)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    panel = await research_employer_with_fetch(
        company=job.company,
        listing_url=job.url,
        source_name=job.source_name,
        posted_at=job.posted_at,
        first_seen_at=job.first_seen_at.isoformat()
        if getattr(job, "first_seen_at", None)
        else None,
        enrichment=job.enrichment if isinstance(job.enrichment, dict) else {},
        fetch=fetch,
    )
    return {"job_id": job_id, "employer": panel}


@router.get("/report-reasons")
async def list_report_reasons(
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "reasons": sorted(ALLOWED_REASONS),
        "note": (
            "Reports queue for human review. They do not auto-exclude listings. "
            "Use the source platform report path when shown."
        ),
    }


@router.post("/jobs/{job_id}/report")
async def report_listing(
    job_id: int,
    body: ListingReportRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    repo = SQLAlchemyJobRepository(session)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    snapshot = TrustIntelligenceService().analyze_job(
        job, include_evidence_records=False
    )
    result = await ListingReportService(session).submit(
        user_id=user.id,
        job_id=job_id,
        reason_code=body.reason_code,
        details=body.details,
        correction_requested=body.correction_requested,
        evidence_snapshot={
            "risk_high_count": snapshot["risk"]["high_count"],
            "extraction_version": snapshot["extraction_meta"]["extraction_version"],
        },
    )
    if not result.get("ok"):
        code = result.get("error")
        if code == "duplicate_report":
            raise HTTPException(status_code=409, detail=result.get("detail"))
        if code == "rate_limited":
            raise HTTPException(status_code=429, detail="Too many reports")
        raise HTTPException(status_code=400, detail=code or "report_failed")
    return result


@router.post("/reports/{report_id}/correction")
async def request_report_correction(
    report_id: int,
    body: CorrectionRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    result = await ListingReportService(session).request_correction(
        report_id=report_id, user_id=user.id, message=body.message
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=403 if result.get("error") == "forbidden" else 400,
            detail=result.get("error"),
        )
    return result


@router.get("/moderation/queue")
async def moderation_queue(
    user: Annotated[User, Depends(require_roles("marketplace_moderator"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query("open"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    items = await ListingReportService(session).list_queue(status=status, limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/moderation/reports/{report_id}/review")
async def review_report(
    report_id: int,
    body: ReportReviewRequest,
    user: Annotated[User, Depends(require_roles("marketplace_moderator"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    result = await ListingReportService(session).review(
        report_id=report_id,
        moderator_user_id=user.id,
        outcome=body.outcome,
        notes=body.notes,
        new_status=body.status,
        commit=False,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=404 if result.get("error") == "not_found" else 400, detail=result.get("error"))
    session.add(AuditEvent(action="listing_report_reviewed", user_id=user.id, meta={
        "report_id": report_id, "outcome": body.outcome, "status": body.status,
        "reason": body.notes[:500] if body.notes else None,
    }))
    await session.commit()
    return result
