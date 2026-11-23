"""Least-privilege marketplace operations and support queue."""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_roles
from backend.application.services.trust.listing_reports import sanitize_report_text
from database.core.session import get_db
from database.models.audit import AuditEvent
from database.models.contracts import ContractDispute, ContractDisputeAddendum, ContractEvent, ProjectContract
from database.models.job import JobRecord
from database.models.lead_action import UserLeadAction
from database.models.listing_report import ListingReport
from database.models.matching import ProjectOffer
from database.models.network import MarketplaceReport, VerificationClaim, VerificationEvidence
from database.models.operations import MarketplaceSupportCase, MarketplaceWaitlistEntry
from database.models.product_event import ProductEvent
from database.models.project import NativeProject, ProjectCandidateShortlist, ProjectModerationQueue
from database.models.user import User
from backend.application.services.network.org_service import OrgService
from app.product_events import PRODUCT_EVENT_NAMES

router = APIRouter(prefix="/ops", tags=["marketplace-operations"])
moderator = require_roles("marketplace_moderator")
support_staff = require_roles("support_agent")
source_staff = require_roles("source_operator")


class SupportCaseCreate(BaseModel):
    category: Literal["account", "project", "listing", "safety", "contract", "other"]
    summary: str = Field(min_length=10, max_length=4000)


class SupportCaseResolve(BaseModel):
    status: Literal["in_review", "resolved", "dismissed"]
    resolution_note: str = Field(min_length=5, max_length=2000)


class OperatorRoleChange(BaseModel):
    role: Literal["marketplace_moderator", "support_agent", "source_operator", "user", "client", "freelancer"]
    reason: str = Field(min_length=10, max_length=500)


class ExpireClaimsRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class WaitlistJoin(BaseModel):
    persona: Literal["client", "freelancer"]
    waitlist_consent: Literal[True]
    concierge_consent: bool = False


class SourceControl(BaseModel):
    disabled: bool
    reason: str = Field(min_length=10, max_length=500)


class VerificationReview(BaseModel):
    status: Literal["verified", "rejected", "revoked"]
    reason: str = Field(min_length=10, max_length=1000)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_expiration(self):
        if self.expires_at and (self.expires_at.tzinfo is None or self.status != "verified" or self.expires_at <= datetime.now(timezone.utc)):
            raise ValueError("Only verified claims may receive a future expiry date")
        return self


class DisputeResolution(BaseModel):
    outcome: Literal["resolved_client", "resolved_freelancer", "no_action"]
    resolution_note: str = Field(min_length=10, max_length=3000)


class DisputeAppeal(BaseModel):
    statement: str = Field(min_length=10, max_length=3000)


class MarketplaceReportResolution(BaseModel):
    status: Literal["resolved", "dismissed", "in_review"]
    resolution_note: str = Field(min_length=10, max_length=2000)


@router.get("/sources")
async def operations_sources(actor: Annotated[User, Depends(source_staff)]) -> dict:
    from app.ingestion.governance import list_policies
    return {"sources": [p.to_dict() for p in list_policies(include_disabled=True)]}


@router.post("/sources/{source_key}")
async def set_source_control(source_key: str, payload: SourceControl, actor: Annotated[User, Depends(source_staff)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    from app.ingestion.governance import get_typed_registry, set_operator_disabled
    from app.ingestion.sources import SOURCE_REGISTRY
    if source_key not in SOURCE_REGISTRY:
        raise HTTPException(404, "Unknown source")
    safe_reason = sanitize_report_text(payload.reason, limit=400) or "Operator source policy change"
    action = "source_operator_disabled" if payload.disabled else "source_operator_enabled"
    db.add(AuditEvent(action=action, user_id=actor.id, meta={"source_key": source_key, "reason": safe_reason}))
    await db.commit()
    set_operator_disabled(source_key, payload.disabled)
    policy = get_typed_registry().get(source_key)
    return {"source": source_key, "operator_disabled": payload.disabled, "policy": policy.to_dict() if policy else None}


@router.post("/waitlist", status_code=201)
async def join_waitlist(payload: WaitlistJoin, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    existing = (await db.execute(select(MarketplaceWaitlistEntry).where(
        MarketplaceWaitlistEntry.user_id == actor.id,
        MarketplaceWaitlistEntry.persona == payload.persona,
    ))).scalar_one_or_none()
    if existing:
        if existing.status == "opted_out":
            raise HTTPException(409, "This waitlist entry was opted out; contact support if you want to rejoin")
        return {"entry_id": existing.id, "status": existing.status, "concierge_consent": existing.concierge_consent}
    recent = await db.scalar(select(func.count(MarketplaceWaitlistEntry.id)).where(
        MarketplaceWaitlistEntry.user_id == actor.id,
        MarketplaceWaitlistEntry.created_at >= datetime.now(timezone.utc).replace(day=1),
    ))
    if int(recent or 0) >= 2:
        raise HTTPException(429, "Waitlist requests are limited to two per month")
    entry = MarketplaceWaitlistEntry(id=str(uuid4()), user_id=actor.id, persona=payload.persona,
                                     concierge_consent=payload.concierge_consent)
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Waitlist entry already exists")
    return {"entry_id": entry.id, "status": entry.status, "concierge_consent": entry.concierge_consent}


@router.get("/waitlist/mine")
async def my_waitlist(actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    entries = (await db.execute(select(MarketplaceWaitlistEntry).where(MarketplaceWaitlistEntry.user_id == actor.id).order_by(MarketplaceWaitlistEntry.created_at.desc()))).scalars().all()
    return {"items": [{"id": x.id, "persona": x.persona, "status": x.status, "concierge_consent": x.concierge_consent} for x in entries]}


@router.delete("/waitlist/{entry_id}")
async def leave_waitlist(entry_id: str, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    entry = await db.get(MarketplaceWaitlistEntry, entry_id)
    if not entry or entry.user_id != actor.id:
        raise HTTPException(404, "Waitlist entry not found")
    entry.status = "opted_out"
    entry.concierge_consent = False
    entry.updated_at = datetime.now(timezone.utc)
    db.add(AuditEvent(action="marketplace_waitlist_opt_out", user_id=actor.id, meta={"entry_id": entry.id}))
    await db.commit()
    return {"entry_id": entry.id, "status": entry.status, "concierge_consent": False}


@router.get("/waitlist/summary")
async def waitlist_summary(actor: Annotated[User, Depends(require_roles("marketplace_moderator", "support_agent"))], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    rows = await db.execute(select(MarketplaceWaitlistEntry.persona, func.count(MarketplaceWaitlistEntry.id)).where(
        MarketplaceWaitlistEntry.status == "waitlisted"
    ).group_by(MarketplaceWaitlistEntry.persona))
    by_persona = {persona: int(count) for persona, count in rows.all()}
    opted_in = await db.scalar(select(func.count(MarketplaceWaitlistEntry.id)).where(
        MarketplaceWaitlistEntry.status == "waitlisted", MarketplaceWaitlistEntry.concierge_consent.is_(True)
    ))
    return {"counts_by_persona": by_persona, "concierge_contact_consented": int(opted_in or 0),
            "data_source": "persisted opt-in records", "customer_count_claim": False}


def _rate_metric(name: str, numerator: int, denominator: int, cohort_size: int, basis: str) -> dict:
    published = cohort_size >= 10 and denominator > 0
    return {
        "name": name,
        "value": (numerator / denominator) if published else None,
        "numerator": numerator if published else None,
        "denominator": denominator if published else None,
        "sample_size": cohort_size if published else "<10; suppressed",
        "status": "measured" if published else ("no_observations" if cohort_size == 0 else "suppressed_small_cohort"),
        "basis": basis,
    }


def _product_event_cell(event_count: int, people: int) -> dict:
    if people < 10:
        return {"events": None, "people": None,
                "status": "no_observations" if people == 0 else "suppressed_small_cohort"}
    return {"events": event_count, "people": people, "status": "measured"}


@router.get("/metrics")
async def operations_metrics(
    actor: Annotated[User, Depends(moderator)],
    db: Annotated[AsyncSession, Depends(get_db)],
    since: datetime | None = Query(None),
) -> dict:
    """Privacy-suppressed outcomes from persisted operational records; missing instrumentation stays null."""
    if since and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    project_filter = [NativeProject.is_sample.is_(False), NativeProject.status.notin_(["draft"])]
    if since:
        project_filter.append(NativeProject.created_at >= since)
    projects = (await db.execute(select(NativeProject.id, NativeProject.status, NativeProject.created_at, NativeProject.org_id).where(*project_filter))).all()
    project_ids = [row.id for row in projects]
    project_n = len(projects)
    abandoned = sum(row.status in {"expired", "canceled"} for row in projects)
    project_orgs = len({row.org_id for row in projects})
    metrics = [_rate_metric("abandoned_project_rate", abandoned, project_n, project_orgs,
                            "expired or canceled non-sample projects / submitted non-sample projects")]

    if project_ids:
        shortlist_rows = (await db.execute(
            select(NativeProject.id, NativeProject.org_id, NativeProject.created_at, func.min(ProjectCandidateShortlist.created_at))
            .join(ProjectCandidateShortlist, ProjectCandidateShortlist.project_id == NativeProject.id)
            .where(NativeProject.id.in_(project_ids))
            .group_by(NativeProject.id, NativeProject.created_at)
        )).all()
        shortlist_hours = [max(0.0, (first_shortlist - created).total_seconds() / 3600)
                           for _, _, created, first_shortlist in shortlist_rows if created and first_shortlist]
        shortlist_orgs = len({org_id for _, org_id, _, first_shortlist in shortlist_rows if first_shortlist})
        shortlist_ready = shortlist_orgs >= 10 and len(shortlist_hours) >= 10
        metrics.append({"name": "time_to_first_shortlist_hours",
                        "value": median(shortlist_hours) if shortlist_ready else None,
                        "sample_size": shortlist_orgs if shortlist_ready else "<10; suppressed",
                        "status": "measured" if shortlist_ready else "suppressed_small_cohort",
                        "basis": "median project created_at to first persisted shortlist; non-sample projects only"})
        offer_counts = (await db.execute(select(ProjectOffer.status, ProjectOffer.org_id, func.count(ProjectOffer.id))
            .join(NativeProject, NativeProject.id == ProjectOffer.project_id)
            .where(NativeProject.id.in_(project_ids))
            .group_by(ProjectOffer.status, ProjectOffer.org_id))).all()
        statuses: dict[str, int] = {}
        finalized_orgs: set[str] = set()
        for status, org_id, count in offer_counts:
            statuses[status] = statuses.get(status, 0) + int(count)
            if status in {"accepted", "declined", "expired"}:
                finalized_orgs.add(org_id)
        finalized = sum(statuses.get(k, 0) for k in ("accepted", "declined", "expired"))
        metrics.append(_rate_metric("offer_hiring_rate", statuses.get("accepted", 0), finalized, len(finalized_orgs),
                                    "accepted / accepted, declined, or expired offers; superseded offers reported separately"))
        accepted_orgs = (await db.execute(select(ProjectOffer.org_id, func.count(ProjectOffer.id))
            .join(NativeProject, NativeProject.id == ProjectOffer.project_id)
            .where(NativeProject.id.in_(project_ids), ProjectOffer.status == "accepted")
            .group_by(ProjectOffer.org_id))).all()
        hiring_org_count = len(accepted_orgs)
        repeat_org_count = sum(count >= 2 for _, count in accepted_orgs)
        metrics.append(_rate_metric("repeat_hiring_organization_rate", repeat_org_count, hiring_org_count, hiring_org_count,
                                    "organizations with 2+ accepted offers / organizations with at least 1 accepted offer"))
    else:
        metrics.extend([
            _rate_metric("offer_hiring_rate", 0, 0, 0, "accepted / finalized offers"),
            _rate_metric("repeat_hiring_organization_rate", 0, 0, 0, "repeat hiring organizations / hiring organizations"),
            {"name": "time_to_first_shortlist_hours", "value": None, "sample_size": 0, "status": "no_observations", "basis": "persisted shortlist records"},
        ])

    clicked_query = select(func.count(UserLeadAction.id), func.count(func.distinct(UserLeadAction.user_id))).where(UserLeadAction.apply_clicked_at.is_not(None))
    confirmed_query = select(func.count(UserLeadAction.id), func.count(func.distinct(UserLeadAction.user_id))).where(UserLeadAction.applied_confirmed_at.is_not(None))
    if since:
        clicked_query = clicked_query.where(UserLeadAction.apply_clicked_at >= since)
        confirmed_query = confirmed_query.where(UserLeadAction.applied_confirmed_at >= since)
    clicks, click_users = (await db.execute(clicked_query)).one()
    confirmed_query = confirmed_query.where(UserLeadAction.apply_clicked_at.is_not(None))
    confirms, confirm_users = (await db.execute(confirmed_query)).one()
    metrics.append(_rate_metric("external_application_confirmation_rate", int(confirms), int(clicks), int(click_users),
                                "confirmed applications / external apply clicks; persisted user lead actions; distinct clicking users determine suppression"))

    listing_window = [JobRecord.is_expired.is_(False)]
    if since:
        listing_window.append(JobRecord.created_at >= since)
    active_jobs = await db.scalar(select(func.count(JobRecord.id)).where(*listing_window))
    active_listing_orgs = await db.scalar(select(func.count(func.distinct(JobRecord.company))).where(
        *listing_window, JobRecord.company.is_not(None)))
    complaint_query = select(func.count(func.distinct(ListingReport.job_id))).join(
        JobRecord, JobRecord.id == ListingReport.job_id
    ).where(ListingReport.moderator_outcome == "confirmed_concern",
            ListingReport.reason_code.in_(["misleading_or_duplicate", "suspicious_link"]), *listing_window)
    if since:
        complaint_query = complaint_query.where(ListingReport.created_at >= since)
    confirmed_complaints = int(await db.scalar(complaint_query) or 0)
    metrics.append(_rate_metric("confirmed_listing_authenticity_complaint_rate", confirmed_complaints,
                                int(active_jobs or 0), int(active_listing_orgs or 0),
                                "human-confirmed listing reports / active external listings; duplicate reports are not deduplicated yet"))

    contract_query = select(func.count(ProjectContract.id)).where(
        ProjectContract.client_ack_at.is_not(None), ProjectContract.freelancer_ack_at.is_not(None))
    if since:
        contract_query = contract_query.where(ProjectContract.created_at >= since)
    active_contracts = int(await db.scalar(contract_query) or 0)
    contract_org_query = select(func.count(func.distinct(ProjectContract.org_id))).where(
        ProjectContract.client_ack_at.is_not(None), ProjectContract.freelancer_ack_at.is_not(None))
    if since:
        contract_org_query = contract_org_query.where(ProjectContract.created_at >= since)
    contract_orgs = int(await db.scalar(contract_org_query) or 0)
    dispute_query = select(func.count(func.distinct(ContractDispute.contract_id)))
    if since:
        dispute_query = dispute_query.where(ContractDispute.created_at >= since)
    disputed_contracts = int(await db.scalar(dispute_query) or 0)
    metrics.append(_rate_metric("contract_dispute_rate", disputed_contracts, active_contracts, contract_orgs,
                                "contracts with a filed report / bilaterally acknowledged contracts; payment dispute is not implied"))

    unavailable = [
        {"name": name, "value": None, "sample_size": None, "status": "not_instrumented", "basis": note}
        for name, note in [
            ("time_to_first_qualified_lead", "No persisted client candidate-exposure timestamp"),
            ("client_review_minutes", "No active review timer events"),
            ("freelancer_time_per_qualified_application", "No freelancer time instrumentation"),
            ("invitation_response_rate", "Invitation delivery confirmation is not a reliable denominator"),
            ("verified_listing_coverage", "Verified authenticity numerator and controlled listing denominator are incomplete"),
            ("newcomer_organic_visibility", "Shortlist impression events are not persisted"),
            ("user_acquisition_cost", "Founder hours and channel spend are not captured in a cost ledger"),
            ("gross_margin", "No native marketplace revenue or full variable-cost ledger"),
            ("effective_payment_cost", "No payment provider transactions are integrated"),
        ]
    ]
    return {"window_start": since.isoformat() if since else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "persisted_records_only", "test_data_policy": "non-sample native projects only; external user actions have no synthetic marker",
            "metrics": metrics + unavailable,
            "instrumentation_status": "partial; do not use as a liquidity, launch-readiness, or customer-count claim"}


@router.get("/product-learning")
async def product_learning_snapshot(
    actor: Annotated[User, Depends(moderator)],
    db: Annotated[AsyncSession, Depends(get_db)],
    since: datetime | None = Query(None),
) -> dict:
    """Aggregate consented product events without exposing actor or event identifiers."""
    if since and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    query = select(
        ProductEvent.environment,
        ProductEvent.event_name,
        func.count(ProductEvent.id),
        func.count(func.distinct(ProductEvent.user_id)),
    )
    if since:
        query = query.where(ProductEvent.occurred_at >= since)
    query = query.group_by(ProductEvent.environment, ProductEvent.event_name)
    rows = (await db.execute(query)).all()
    environments: dict[str, dict[str, dict]] = {
        environment: {name: _product_event_cell(0, 0) for name in PRODUCT_EVENT_NAMES}
        for environment in ("production", "staging", "test", "development")
    }
    for environment, event_name, event_count, people in rows:
        environments.setdefault(environment, {})[event_name] = _product_event_cell(int(event_count), int(people))
    return {
        "window_start": since.isoformat() if since else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "consented_product_events_only",
        "environments": environments,
        "dictionary": sorted(PRODUCT_EVENT_NAMES),
        "limitations": [
            "No user-level rows or properties are returned.",
            "Small cohorts are suppressed; absence means unknown, not zero.",
            "Self-reported application, interview, contract, and cash outcomes are not verified ground truth.",
            "Event instrumentation is not yet wired to every product workflow; do not treat counts as complete funnels.",
        ],
    }


@router.post("/support-cases", status_code=201)
async def create_support_case(payload: SupportCaseCreate, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    open_count = await db.scalar(select(func.count(MarketplaceSupportCase.id)).where(
        MarketplaceSupportCase.requester_user_id == actor.id,
        MarketplaceSupportCase.status.in_(["open", "in_review"])))
    if int(open_count or 0) >= 5:
        raise HTTPException(429, "Please wait for an existing support case to be reviewed")
    case = MarketplaceSupportCase(id=str(uuid4()), requester_user_id=actor.id, category=payload.category,
                                  summary=sanitize_report_text(payload.summary, limit=2000) or "Support request")
    db.add(case)
    await db.commit()
    return {"case_id": case.id, "status": case.status, "message": "Your request is queued for human support."}


@router.get("/support-cases/mine")
async def my_support_cases(actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    rows = (await db.execute(select(MarketplaceSupportCase).where(
        MarketplaceSupportCase.requester_user_id == actor.id
    ).order_by(MarketplaceSupportCase.created_at.desc()).limit(50))).scalars().all()
    return {"items": [{"id": x.id, "category": x.category, "status": x.status,
                       "created_at": x.created_at.isoformat() if x.created_at else None,
                       "resolution_note": x.resolution_note} for x in rows]}


@router.get("/queues")
async def operations_queues(
    actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    project_rows = (await db.execute(select(ProjectModerationQueue).where(
        ProjectModerationQueue.status.in_(["pending_review", "under_review", "appealed"])
    ).order_by(ProjectModerationQueue.created_at).limit(limit))).scalars().all()
    report_rows = (await db.execute(select(ListingReport).where(
        ListingReport.status.in_(["open", "in_review"])
    ).order_by(ListingReport.created_at).limit(limit))).scalars().all()
    claim_rows = (await db.execute(select(VerificationClaim).where(
        VerificationClaim.status.in_(["pending", "under_review"])
    ).order_by(VerificationClaim.created_at).limit(limit))).scalars().all()
    return {
        "projects": [{"id": x.id, "project_id": x.project_id, "reason": x.reason_code, "status": x.status, "appeal_summary": sanitize_report_text(x.appeal_details, limit=600), "created_at": x.created_at.isoformat() if x.created_at else None} for x in project_rows],
        "listing_reports": [{"id": x.id, "job_id": x.job_id, "reason": x.reason_code, "status": x.status, "summary": x.sanitized_details, "created_at": x.created_at.isoformat() if x.created_at else None} for x in report_rows],
        "marketplace_reports": await _marketplace_report_queue(db, limit),
        "verification_claims": [{"id": x.id, "claim_type": x.claim_type, "status": x.status, "created_at": x.created_at.isoformat() if x.created_at else None} for x in claim_rows],
        "payment_exceptions": {"available": False, "reason": "No payment provider is integrated"},
        "privacy": "Queue payload omits reporter identity and private evidence. Open a case through its authorized detail workflow to access necessary records.",
    }


async def _marketplace_report_queue(db: AsyncSession, limit: int) -> list[dict]:
    rows = (await db.execute(select(MarketplaceReport).where(
        MarketplaceReport.status.in_(["opened", "in_review"])
    ).order_by(MarketplaceReport.created_at).limit(limit))).scalars().all()
    return [{"id": x.id, "target_type": x.target_type, "target_id": x.target_id,
             "report_type": x.report_type, "reason": x.reason, "status": x.status,
             "created_at": x.created_at.isoformat() if x.created_at else None} for x in rows]


@router.get("/marketplace-reports/{report_id}")
async def get_marketplace_report(report_id: str, actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    report = await db.get(MarketplaceReport, report_id)
    if not report:
        raise HTTPException(404, "Marketplace report not found")
    db.add(AuditEvent(action="marketplace_report_details_accessed", user_id=actor.id, meta={"report_id": report.id}))
    await db.commit()
    return {"id": report.id, "target_type": report.target_type, "target_id": report.target_id,
            "report_type": report.report_type, "reason": report.reason,
            "details": sanitize_report_text(report.details, limit=1500), "status": report.status}


@router.post("/marketplace-reports/{report_id}/resolve")
async def resolve_marketplace_report(report_id: str, payload: MarketplaceReportResolution, actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    report = await db.get(MarketplaceReport, report_id)
    if not report:
        raise HTTPException(404, "Marketplace report not found")
    if report.status not in {"opened", "in_review"}:
        raise HTTPException(409, "Report is already resolved")
    note = sanitize_report_text(payload.resolution_note, limit=1500) or "Human review completed"
    report.status = payload.status
    report.resolution_notes = note
    report.resolved_by_id = actor.id
    report.updated_at = datetime.now(timezone.utc)
    db.add(AuditEvent(action="marketplace_report_resolved", user_id=actor.id,
        meta={"report_id": report.id, "status": report.status, "reason": note}))
    await db.commit()
    return {"id": report.id, "status": report.status, "reviewer": "human"}


@router.get("/support-queue")
async def support_queue(actor: Annotated[User, Depends(support_staff)], db: Annotated[AsyncSession, Depends(get_db)], limit: int = Query(50, ge=1, le=100)) -> dict:
    cases = (await db.execute(select(MarketplaceSupportCase).where(
        MarketplaceSupportCase.status.in_(["open", "in_review"])
    ).order_by(MarketplaceSupportCase.created_at).limit(limit))).scalars().all()
    disputes = (await db.execute(select(ContractDispute).where(
        ContractDispute.state.in_(["open", "appealed"])
    ).order_by(ContractDispute.created_at).limit(limit))).scalars().all()
    return {"cases": [{"id": x.id, "category": x.category, "status": x.status, "summary": x.summary, "created_at": x.created_at.isoformat() if x.created_at else None} for x in cases],
            "disputes": [{"id": x.id, "contract_id": x.contract_id, "reason": x.reason, "status": x.state, "created_at": x.created_at.isoformat() if x.created_at else None} for x in disputes],
            "payment_exceptions": {"available": False, "reason": "No payment provider is integrated"}}


@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(dispute_id: str, payload: DisputeResolution, actor: Annotated[User, Depends(support_staff)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    dispute = await db.get(ContractDispute, dispute_id)
    if not dispute:
        raise HTTPException(404, "Dispute not found")
    if dispute.state not in {"open", "appealed"}:
        raise HTTPException(409, "Dispute is not awaiting human review")
    dispute.state = "resolved"
    dispute.resolution_note = sanitize_report_text(payload.resolution_note, limit=2500)
    dispute.resolved_by_id = actor.id
    dispute.resolved_at = datetime.now(timezone.utc)
    db.add(ContractEvent(id=str(uuid4()), contract_id=dispute.contract_id, actor_id=actor.id,
        event_type="dispute_human_outcome", payload={"dispute_id": dispute.id, "outcome": payload.outcome,
        "note": dispute.resolution_note, "provider_escalation": "unsupported"}))
    db.add(AuditEvent(action="contract_dispute_resolved", user_id=actor.id,
        meta={"dispute_id": dispute.id, "outcome": payload.outcome, "reason": dispute.resolution_note}))
    await db.commit()
    return {"dispute_id": dispute.id, "status": dispute.state, "reviewer": "human", "provider_escalation": "unsupported"}


@router.get("/disputes/{dispute_id}")
async def dispute_detail(dispute_id: str, actor: Annotated[User, Depends(support_staff)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    dispute = await db.get(ContractDispute, dispute_id)
    if not dispute:
        raise HTTPException(404, "Dispute not found")
    addenda = (await db.execute(select(ContractDisputeAddendum).where(
        ContractDisputeAddendum.dispute_id == dispute.id
    ).order_by(ContractDisputeAddendum.created_at))).scalars().all()
    db.add(AuditEvent(action="contract_dispute_evidence_accessed", user_id=actor.id, meta={"dispute_id": dispute.id}))
    await db.commit()
    return {"id": dispute.id, "contract_id": dispute.contract_id, "reason": dispute.reason,
            "statement": sanitize_report_text(dispute.statement, limit=3000), "evidence": dispute.evidence,
            "addenda": [{"statement": sanitize_report_text(x.statement, limit=2500), "evidence": x.evidence,
                         "created_at": x.created_at.isoformat() if x.created_at else None} for x in addenda]}


@router.post("/disputes/{dispute_id}/appeal")
async def appeal_dispute(dispute_id: str, payload: DisputeAppeal, actor: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    dispute = await db.get(ContractDispute, dispute_id)
    if not dispute:
        raise HTTPException(404, "Dispute not found")
    contract = await db.get(ProjectContract, dispute.contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")
    is_party = actor.id == contract.freelancer_id or await OrgService(db).verify_user_in_org(contract.org_id, actor.id)
    if not is_party:
        raise HTTPException(403, "Only contract participants may appeal")
    if dispute.state != "resolved":
        raise HTTPException(409, "Only a documented human outcome can be appealed")
    dispute.state = "appealed"
    statement = sanitize_report_text(payload.statement, limit=2500) or "Appeal submitted"
    db.add(ContractEvent(id=str(uuid4()), contract_id=contract.id, actor_id=actor.id,
        event_type="dispute_appealed", payload={"dispute_id": dispute.id, "statement": statement, "review": "human_required"}))
    db.add(AuditEvent(action="contract_dispute_appealed", user_id=actor.id,
        meta={"dispute_id": dispute.id, "reason": statement}))
    await db.commit()
    return {"dispute_id": dispute.id, "status": dispute.state, "review": "human_required", "provider_escalation": "unsupported"}


@router.post("/verification/expire-due")
async def expire_due_claims(payload: ExpireClaimsRequest, actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    now = datetime.now(timezone.utc)
    rows = (await db.execute(select(VerificationClaim).where(
        VerificationClaim.status == "verified", VerificationClaim.expires_at.is_not(None), VerificationClaim.expires_at <= now
    ))).scalars().all()
    for claim in rows:
        claim.status = "expired"
    db.add(AuditEvent(action="verification_claims_expired", user_id=actor.id,
                      meta={"count": len(rows), "reason": sanitize_report_text(payload.reason, limit=400)}))
    await db.commit()
    return {"expired_count": len(rows), "checked_at": now.isoformat()}


@router.get("/verification/claims/{claim_id}")
async def verification_claim_detail(claim_id: str, actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    claim = await db.get(VerificationClaim, claim_id)
    if not claim:
        raise HTTPException(404, "Verification claim not found")
    evidence = (await db.execute(select(VerificationEvidence).where(VerificationEvidence.claim_id == claim.id))).scalars().all()
    db.add(AuditEvent(action="verification_claim_evidence_accessed", user_id=actor.id, meta={"claim_id": claim.id}))
    await db.commit()
    return {"id": claim.id, "claim_type": claim.claim_type, "status": claim.status,
            "evidence": [{"id": e.id, "provider": e.provider, "evidence_type": e.evidence_type,
                          "is_valid": e.is_valid, "submitted_at": e.submitted_at.isoformat() if e.submitted_at else None,
                          "provider_reference_present": bool(e.provider_reference_id)} for e in evidence]}


@router.post("/verification/claims/{claim_id}/review")
async def review_verification_claim(claim_id: str, payload: VerificationReview, actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    claim = await db.get(VerificationClaim, claim_id)
    if not claim:
        raise HTTPException(404, "Verification claim not found")
    if claim.status not in {"pending", "under_review", "verified"}:
        raise HTTPException(409, "Claim is not reviewable")
    claim.status = payload.status
    claim.reviewer_notes = sanitize_report_text(payload.reason, limit=900)
    claim.expires_at = payload.expires_at
    claim.verified_at = datetime.now(timezone.utc) if payload.status == "verified" else None
    db.add(AuditEvent(action="verification_claim_reviewed", user_id=actor.id, meta={
        "claim_id": claim.id, "status": claim.status, "expires_at": claim.expires_at.isoformat() if claim.expires_at else None,
        "reason": claim.reviewer_notes,
    }))
    await db.commit()
    return {"claim_id": claim.id, "status": claim.status, "expires_at": claim.expires_at.isoformat() if claim.expires_at else None}


@router.post("/support-cases/{case_id}/resolve")
async def resolve_support_case(case_id: str, payload: SupportCaseResolve, actor: Annotated[User, Depends(support_staff)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    case = await db.get(MarketplaceSupportCase, case_id)
    if not case:
        raise HTTPException(404, "Support case not found")
    case.status = payload.status
    case.assigned_to_id = actor.id
    case.resolution_note = sanitize_report_text(payload.resolution_note, limit=1500)
    case.updated_at = datetime.now(timezone.utc)
    db.add(AuditEvent(action="support_case_updated", user_id=actor.id, meta={"case_id": case.id, "status": case.status, "reason": case.resolution_note}))
    await db.commit()
    return {"case_id": case.id, "status": case.status}


@router.post("/users/{user_id}/role")
async def set_operator_role(user_id: str, payload: OperatorRoleChange, actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    # Moderators may provision only operational roles; superuser roles remain admin-only.
    if not actor.is_superuser:
        raise HTTPException(403, "Only a superuser may assign operational roles")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == actor.id and payload.role != "user":
        raise HTTPException(400, "Do not assign an operator role to yourself")
    previous = user.account_role
    user.account_role = payload.role
    db.add(AuditEvent(action="operator_role_changed", user_id=actor.id,
                      meta={"target_user_id": user.id, "from": previous, "to": payload.role, "reason": sanitize_report_text(payload.reason, limit=400)}))
    await db.commit()
    return {"user_id": user.id, "account_role": user.account_role}


@router.get("/audit")
async def operations_audit(actor: Annotated[User, Depends(moderator)], db: Annotated[AsyncSession, Depends(get_db)], limit: int = Query(100, ge=1, le=250)) -> dict:
    # Log the sensitive read itself before returning prior actions.
    db.add(AuditEvent(action="operations_audit_read", user_id=actor.id, meta={"limit": limit}))
    await db.commit()
    rows = (await db.execute(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit))).scalars().all()
    return {"items": [{"id": x.id, "action": x.action, "actor_id": x.user_id, "meta": x.meta, "created_at": x.created_at.isoformat() if x.created_at else None} for x in rows]}
