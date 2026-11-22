"""Phase 15 — Fair two-sided marketplace matching, mutual interest, direct negotiation, and concurrency-safe offers API.

Private preview feature flag enforced until Gate 18.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from backend.application.services.marketplace_matching import (
    CandidateMatch,
    ConflictError,
    EvaluationMetricsCalculator,
    FairMarketplaceMatcher,
    NegotiationAssistant,
    ProjectConversationService,
    ProjectMutualInterestService,
    ProjectNegotiationService,
    TalentFeatureVector,
)
from backend.application.services.network.org_service import OrgService
from backend.application.services.network.profile_service import ProfileService
from config.settings import get_settings
from database.core.session import get_db
from database.models.matching import (
    ProjectApplication,
    ProjectConversation,
    ProjectInvitation,
    ProjectMatchScore,
    ProjectOffer,
)
from database.models.network import (
    PortfolioArtifact,
    RatePreference,
    ReputationActivity,
    TalentProfile,
    TalentSkill,
    WorkAvailability,
)
from database.models.project import NativeProject
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

router = APIRouter(prefix="/matching", tags=["matching"])
settings = get_settings()


def _enforce_marketplace_access(user: User | None = None) -> None:
    if not settings.feature_marketplace_enabled:
        if settings.marketplace_status == "disabled":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Marketplace foundation is disabled.",
            )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Marketplace is in private preview (Gate 18 prerequisite). Sign in required.",
            )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ApplicationCreatePayload(BaseModel):
    structured_pitch: str = Field(min_length=15, max_length=4000)
    proposed_rate: float = Field(ge=0.0)
    proposed_rate_period: Literal["fixed", "hourly", "monthly_retainer"] = "fixed"
    estimated_days: int | None = Field(default=None, ge=1, le=365)
    relevant_artifacts: list[dict[str, Any]] | None = None


class CandidateInvitePayload(BaseModel):
    freelancer_id: str = Field(min_length=1, max_length=36)


class InvitationRespondPayload(BaseModel):
    accept: bool
    decline_reason: str | None = Field(default=None, max_length=256)


class DeclinePayload(BaseModel):
    reason: str | None = Field(default=None, max_length=256)


class SendMessagePayload(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    attachments: list[dict[str, Any]] | None = None


class ConversationReportPayload(BaseModel):
    action: Literal["report", "block"] = "report"
    reason: str = Field(min_length=3, max_length=500)


class NegotiationDraftPayload(BaseModel):
    agreed_amount: float = Field(gt=0.0)
    contract_type: Literal["fixed_price", "hourly", "monthly_retainer"] = "fixed_price"
    proposed_milestones: list[dict[str, Any]] | None = None
    custom_scope: str | None = Field(default=None, max_length=4000)


class OfferCreatePayload(BaseModel):
    application_id: str = Field(min_length=1, max_length=36)
    agreed_amount: float = Field(gt=0.0)
    contract_type: Literal["fixed_price", "hourly", "monthly_retainer"] = "fixed_price"
    milestones: list[dict[str, Any]] | None = None
    scope_summary: str | None = Field(default=None, max_length=4000)
    decision_deadline_days: int = Field(default=7, ge=1, le=30)
    conversation_id: str | None = None


class OfferCounterPayload(BaseModel):
    revised_amount: float = Field(gt=0.0)
    change_summary: str = Field(min_length=5, max_length=2000)
    contract_type: Literal["fixed_price", "hourly", "monthly_retainer"] | None = None
    milestones: list[dict[str, Any]] | None = None
    scope_summary: str | None = Field(default=None, max_length=4000)


# ---------------------------------------------------------------------------
# Shortlist & Matching Endpoints
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/shortlist")
async def get_project_shortlist(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=5, ge=1, le=20),
    request_more: bool = Query(default=False),
    more_reason: str | None = Query(default=None),
) -> dict[str, Any]:
    """Client obtains explainable talent matches for their approved native project."""
    _enforce_marketplace_access(user)

    # 1. Load project
    project_res = await session.execute(
        select(NativeProject).where(NativeProject.id == project_id)
    )
    project = project_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Verify client access
    org_service = OrgService(session)
    has_access = await org_service.verify_user_in_org(project.org_id, user.id)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to project")

    # 2. Load published talent profiles
    stmt = (
        select(TalentProfile)
        .where(
            TalentProfile.is_published == True,
            TalentProfile.status == "published",
        )
        .order_by(TalentProfile.created_at.desc())
    )
    profiles_res = await session.execute(stmt)
    profiles = profiles_res.scalars().all()

    # 3. Build Organic Talent Feature Vectors (Firewall Enforced: NO entitlement fields)
    vectors: list[TalentFeatureVector] = []
    for prof in profiles:
        # Load skills
        skills_res = await session.execute(
            select(TalentSkill).where(TalentSkill.profile_id == prof.id)
        )
        skills = skills_res.scalars().all()
        skills_data = [
            {
                "skill_name": s.skill_name,
                "years": s.years_of_experience,
                "verification_status": s.verification_status,
            }
            for s in skills
        ]

        # Load rates
        rate_res = await session.execute(
            select(RatePreference).where(RatePreference.profile_id == prof.id)
        )
        rate = rate_res.scalar_one_or_none()

        # Load availability
        avail_res = await session.execute(
            select(WorkAvailability).where(WorkAvailability.profile_id == prof.id)
        )
        avail = avail_res.scalar_one_or_none()

        # Load portfolio artifacts count
        art_res = await session.execute(
            select(func.count(PortfolioArtifact.id)).where(PortfolioArtifact.profile_id == prof.id)
        )
        art_count = art_res.scalar_one() or 0

        # Build feature vector
        vector = TalentFeatureVector(
            freelancer_id=prof.user_id,
            headline=prof.headline,
            skills=skills_data,
            min_rate=rate.min_rate if rate else 0.0,
            max_rate=rate.max_rate if rate else 0.0,
            rate_type=rate.rate_type if rate else "hourly",
            currency=rate.currency if rate else "USD",
            hours_per_week=avail.hours_per_week if avail else 40,
            availability_status=avail.status if avail else "available",
            work_type_preference="remote",
            years_experience=prof.years_experience or 1.0,
            verification_level=getattr(prof, "verification_level", 2) or 2,
            is_newcomer=bool(getattr(prof, "years_experience", 1.0) <= 3.0),
            portfolio_verified_count=art_count,
            reputation_score=0.9,
        )
        vectors.append(vector)

    # 4. Rank candidates using FairMarketplaceMatcher
    ranked = FairMarketplaceMatcher.rank_candidates(
        project=project,
        talent_vectors=vectors,
        limit=limit,
        request_more=request_more,
        more_reason=more_reason,
    )

    items = []
    for m in ranked:
        items.append({
            "freelancer_id": m.freelancer_id,
            "headline": m.headline,
            "overall_score": m.overall_score,
            "skill_score": m.breakdown.skill_score,
            "budget_score": m.breakdown.budget_score,
            "availability_score": m.breakdown.availability_score,
            "work_pref_score": m.breakdown.work_pref_score,
            "newcomer_boost": m.breakdown.newcomer_boost,
            "reasons": m.breakdown.reasons,
            "missing_information": m.breakdown.missing_information,
            "is_newcomer": m.is_newcomer,
            "verification_level": m.verification_level,
        })

    return {
        "project_id": project.id,
        "shortlist": items,
        "count": len(items),
        "requested_more": request_more,
        "more_reason": more_reason,
    }


# ---------------------------------------------------------------------------
# Mutual Interest & Applications Endpoints
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/apply", status_code=status.HTTP_201_CREATED)
async def submit_expression_of_interest(
    project_id: str,
    payload: ApplicationCreatePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Freelancer submits structured expression of interest at 100% free ($0.00 platform fee)."""
    _enforce_marketplace_access(user)
    service = ProjectMutualInterestService(session)
    try:
        app = await service.submit_expression_of_interest(
            project_id=project_id,
            freelancer_id=user.id,
            structured_pitch=payload.structured_pitch,
            relevant_artifacts=payload.relevant_artifacts,
            proposed_rate=payload.proposed_rate,
            proposed_rate_period=payload.proposed_rate_period,
            estimated_days=payload.estimated_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Expression of interest submitted successfully at $0 fee.",
        "application_id": app.id,
        "status": app.status,
    }


@router.post("/projects/{project_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_talent_to_project(
    project_id: str,
    payload: CandidateInvitePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Client invites candidate from shortlist to consider their project."""
    _enforce_marketplace_access(user)
    service = ProjectMutualInterestService(session)
    try:
        inv = await service.invite_talent(
            project_id=project_id,
            client_user_id=user.id,
            freelancer_id=payload.freelancer_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Candidate invited successfully.",
        "invitation_id": inv.id,
        "expires_at": inv.expires_at.isoformat(),
    }


@router.post("/invitations/{invitation_id}/respond")
async def respond_to_invitation(
    invitation_id: str,
    payload: InvitationRespondPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Freelancer accepts or declines project invitation with no fee or penalty."""
    _enforce_marketplace_access(user)
    service = ProjectMutualInterestService(session)
    try:
        inv = await service.respond_to_invitation(
            invitation_id=invitation_id,
            freelancer_id=user.id,
            accept=payload.accept,
            decline_reason=payload.decline_reason,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": f"Invitation {inv.status}.",
        "status": inv.status,
    }


@router.get("/projects/{project_id}/applications")
async def list_project_applications(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Client reviews expressions of interest for their project."""
    _enforce_marketplace_access(user)
    service = ProjectMutualInterestService(session)
    try:
        items = await service.get_project_applications(project_id, user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {"applications": items, "count": len(items)}


@router.get("/freelancer/applications")
async def list_freelancer_applications(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Freelancer reviews their active and past expressions of interest."""
    _enforce_marketplace_access(user)
    service = ProjectMutualInterestService(session)
    items = await service.get_freelancer_applications(user.id)
    return {"applications": items, "count": len(items)}


@router.post("/applications/{application_id}/withdraw")
async def withdraw_application(
    application_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Freelancer withdraws their expression of interest."""
    _enforce_marketplace_access(user)
    service = ProjectMutualInterestService(session)
    try:
        app = await service.withdraw_expression_of_interest(application_id, user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Application withdrawn successfully.", "status": app.status}


@router.post("/applications/{application_id}/decline")
async def decline_application(
    application_id: str,
    payload: DeclinePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Decline application without negative public rating penalty."""
    _enforce_marketplace_access(user)
    service = ProjectMutualInterestService(session)
    try:
        app = await service.decline_application(application_id, user.id, payload.reason)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": f"Application {app.status}.", "status": app.status}


# ---------------------------------------------------------------------------
# Direct Messaging Endpoints
# ---------------------------------------------------------------------------


@router.post("/conversations/initiate")
async def initiate_conversation(
    project_id: str,
    freelancer_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    application_id: str | None = None,
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectConversationService(session)
    try:
        conv = await service.get_or_create_conversation(
            project_id=project_id,
            freelancer_id=freelancer_id,
            actor_id=user.id,
            application_id=application_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"conversation_id": conv.id, "status": conv.status}


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectConversationService(session)
    try:
        msgs = await service.get_messages(conversation_id, user.id)
        # Mark unread
        await service.mark_as_read(conversation_id, user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {"messages": msgs, "count": len(msgs)}


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_conversation_message(
    conversation_id: str,
    payload: SendMessagePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectConversationService(session)
    try:
        msg = await service.send_message(
            conversation_id=conversation_id,
            sender_id=user.id,
            body=payload.body,
            attachments=payload.attachments,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Message sent.",
        "message_id": msg.id,
        "sender_role": msg.sender_role,
        "body": msg.body,
    }


@router.post("/conversations/{conversation_id}/report")
async def report_or_block_conversation(
    conversation_id: str,
    payload: ConversationReportPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectConversationService(session)
    try:
        conv = await service.report_or_block_conversation(
            conversation_id=conversation_id,
            reporter_id=user.id,
            action=payload.action,
            reason=payload.reason,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": f"Conversation {payload.action}ed.", "status": conv.status}


# ---------------------------------------------------------------------------
# Negotiation & Concurrency-Safe Offers Endpoints
# ---------------------------------------------------------------------------


@router.post("/negotiation/assistant-draft")
async def draft_negotiation_terms(
    payload: NegotiationDraftPayload,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    try:
        terms = NegotiationAssistant.draft_negotiated_terms(
            base_title="Native Project Scope",
            agreed_amount=payload.agreed_amount,
            contract_type=payload.contract_type,
            proposed_milestones=payload.proposed_milestones,
            custom_scope=payload.custom_scope,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"draft_terms": terms}


@router.post("/projects/{project_id}/offers", status_code=status.HTTP_201_CREATED)
async def create_project_offer(
    project_id: str,
    payload: OfferCreatePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectNegotiationService(session)
    try:
        offer = await service.create_offer(
            project_id=project_id,
            application_id=payload.application_id,
            actor_id=user.id,
            agreed_amount=payload.agreed_amount,
            contract_type=payload.contract_type,
            milestones=payload.milestones,
            scope_summary=payload.scope_summary,
            decision_deadline_days=payload.decision_deadline_days,
            conversation_id=payload.conversation_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Offer created in pending review.",
        "offer_id": offer.id,
        "version": offer.version,
        "status": offer.status,
    }


@router.post("/offers/{offer_id}/counter")
async def counter_propose_offer(
    offer_id: str,
    payload: OfferCounterPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectNegotiationService(session)
    try:
        offer = await service.counter_propose_offer(
            offer_id=offer_id,
            actor_id=user.id,
            revised_amount=payload.revised_amount,
            change_summary=payload.change_summary,
            contract_type=payload.contract_type,
            milestones=payload.milestones,
            scope_summary=payload.scope_summary,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": f"Counter-proposal submitted. Offer revised to v{offer.version}.",
        "offer_id": offer.id,
        "version": offer.version,
        "status": offer.status,
    }


@router.post("/offers/{offer_id}/accept")
async def accept_project_offer(
    offer_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Accept offer with strict concurrency locking and conflict protection."""
    _enforce_marketplace_access(user)
    service = ProjectNegotiationService(session)
    try:
        offer = await service.accept_offer(offer_id=offer_id, actor_id=user.id)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Offer accepted successfully! Project position filled.",
        "offer_id": offer.id,
        "status": offer.status,
    }


@router.post("/offers/{offer_id}/decline")
async def decline_project_offer(
    offer_id: str,
    payload: DeclinePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Decline offer. No negative public rating penalty."""
    _enforce_marketplace_access(user)
    service = ProjectNegotiationService(session)
    try:
        offer = await service.decline_offer(offer_id=offer_id, actor_id=user.id, reason=payload.reason)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Offer declined.", "status": offer.status}


@router.get("/projects/{project_id}/offers")
async def list_project_offers(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectNegotiationService(session)
    try:
        items = await service.get_project_offers(project_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {"offers": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Evaluation Metrics & Synthetic Liquidity Disclaimer
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def get_marketplace_metrics(
    user: Annotated[User, Depends(get_current_user)],
    mode: Literal["simulated", "actual"] = Query(default="simulated"),
) -> dict[str, Any]:
    """Provides privacy-safe evaluation metrics with synthetic liquidity disclaimers."""
    _enforce_marketplace_access(user)
    metrics = EvaluationMetricsCalculator.calculate_benchmark(sample_size=25, mode=mode)
    return {"metrics": metrics.to_dict()}
