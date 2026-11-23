"""Phase 14 — Native client workspace, project brief lifecycle, hiring intent, and moderation queue API.

Feature flagged native marketplace kept private until Gate 18.
Native project listings are strictly distinct from external raw scraped leads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_superuser, get_current_user, require_roles
from backend.application.services.network.org_service import OrgService
from backend.application.services.project import (
    ClarificationService,
    ModerationService,
    ProjectService,
    STANDARDIZED_PROJECT_TEMPLATES,
    ScopeClarificationEngine,
)
from config.settings import get_settings
from database.core.session import get_db
from database.models.audit import AuditEvent
from database.models.project import PROJECT_LIFECYCLE_STAGES
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

router = APIRouter(prefix="/projects", tags=["projects"])
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


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------


class ScopeClarifyRequest(BaseModel):
    raw_description: str = Field(min_length=10, max_length=10000)
    template_key: str | None = None
    skills_hint: list[str] | None = None


class ProjectCreatePayload(BaseModel):
    org_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=3, max_length=256)
    raw_description: str = Field(min_length=10, max_length=10000)
    budget_min: float = Field(gt=0.0)
    budget_max: float = Field(gt=0.0)
    hiring_deadline: datetime
    currency: str = Field(default="USD", min_length=3, max_length=8)
    rate_period: Literal["hourly", "fixed", "monthly_retainer"] = "fixed"
    scope_level: Literal["small", "medium", "large", "enterprise"] = "medium"
    work_type: Literal["remote", "hybrid", "onsite"] = "remote"
    commitment_type: Literal["contract", "full_time", "part_time"] = "contract"
    required_hours_per_week: int = Field(default=20, ge=1, le=168)
    skills_required: list[str] | None = None
    acceptance_criteria: list[str] | None = None
    milestone_outline: list[dict[str, Any]] | None = None
    template_key: str | None = None
    is_sample: bool = False


class ApproveScopePayload(BaseModel):
    custom_summary: str | None = Field(default=None, max_length=10000)


class TransitionPayload(BaseModel):
    target_status: str
    reason: str | None = Field(default=None, max_length=256)
    metadata: dict[str, Any] | None = None


class ShortlistPayload(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=36)
    notes: str | None = Field(default=None, max_length=2000)


class CandidateStagePayload(BaseModel):
    stage: Literal["shortlisted", "interviewing", "offered", "hired", "declined"]
    notes: str | None = Field(default=None, max_length=2000)


class ClarificationQuestionPayload(BaseModel):
    question: str = Field(min_length=10, max_length=2000)


class ClarificationAnswerPayload(BaseModel):
    answer: str = Field(min_length=2, max_length=4000)
    is_public: bool = True


class AppealPayload(BaseModel):
    appeal_details: str = Field(min_length=10, max_length=4000)


class ModerationDecisionPayload(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer_notes: str = Field(min_length=10, max_length=4000)


# -------------------------------------------------------------------------
# Wizard & Templates Endpoints
# -------------------------------------------------------------------------


@router.get("/templates")
async def get_templates(
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    return {"templates": STANDARDIZED_PROJECT_TEMPLATES}


@router.post("/clarify-scope")
async def clarify_project_scope(
    payload: ScopeClarifyRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    clarified = ScopeClarificationEngine.clarify_scope(
        raw_description=payload.raw_description,
        template_key=payload.template_key,
        skills_hint=payload.skills_hint,
    )
    return {"clarification": clarified}


# -------------------------------------------------------------------------
# Project Lifecycle Endpoints
# -------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreatePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    try:
        project = await service.create_project_brief(
            org_id=payload.org_id,
            creator_id=user.id,
            title=payload.title,
            raw_description=payload.raw_description,
            budget_min=payload.budget_min,
            budget_max=payload.budget_max,
            hiring_deadline=payload.hiring_deadline,
            currency=payload.currency,
            rate_period=payload.rate_period,
            scope_level=payload.scope_level,
            work_type=payload.work_type,
            commitment_type=payload.commitment_type,
            required_hours_per_week=payload.required_hours_per_week,
            skills_required=payload.skills_required,
            acceptance_criteria=payload.acceptance_criteria,
            milestone_outline=payload.milestone_outline,
            template_key=payload.template_key,
            is_sample=payload.is_sample,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": "Project brief created in draft",
        "project": {
            "id": project.id,
            "org_id": project.org_id,
            "title": project.title,
            "status": project.status,
            "ai_clarification_approved": project.ai_clarification_approved,
            "ai_scope_summary": project.ai_scope_summary,
            "budget_min": project.budget_min,
            "budget_max": project.budget_max,
            "currency": project.currency,
            "hiring_deadline": project.hiring_deadline.isoformat(),
        },
    }


@router.get("")
async def list_projects(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    org_id: str | None = Query(default=None),
    view: Literal["client", "freelancer"] = Query(default="client"),
    status_filter: str | None = Query(default=None),
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)

    from sqlalchemy import select

    if view == "client":
        # Client view: projects belonging to user's orgs
        orgs = await service.org_service.get_user_organizations(user.id)
        accessible_org_ids = [o["org_id"] for o in orgs]
        if org_id:
            if org_id not in accessible_org_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to organization")
            accessible_org_ids = [org_id]

        stmt = select(service.session.bind.__class__)  # placeholder
        from database.models.project import NativeProject

        stmt = select(NativeProject).where(NativeProject.org_id.in_(accessible_org_ids)).order_by(NativeProject.created_at.desc())
        if status_filter:
            stmt = stmt.where(NativeProject.status == status_filter)

        res = await session.execute(stmt)
        projects = res.scalars().all()

        items = []
        for p in projects:
            items.append({
                "id": p.id,
                "org_id": p.org_id,
                "title": p.title,
                "status": p.status,
                "review_state": p.review_state,
                "scope_level": p.scope_level,
                "budget_min": p.budget_min,
                "budget_max": p.budget_max,
                "currency": p.currency,
                "rate_period": p.rate_period,
                "hiring_deadline": p.hiring_deadline.isoformat(),
                "reconfirm_by": p.reconfirm_by.isoformat(),
                "created_at": p.created_at.isoformat(),
            })
        return {"projects": items, "count": len(items)}

    else:
        # Freelancer view: active approved_open projects with observable hiring intent evidence
        from database.models.project import NativeProject

        stmt = (
            select(NativeProject)
            .where(NativeProject.status == "approved_open", NativeProject.is_sample == False)
            .order_by(NativeProject.created_at.desc())
        )
        res = await session.execute(stmt)
        projects = res.scalars().all()

        items = []
        for p in projects:
            org = await service.org_service.get_org_by_id(p.org_id)
            intent = service.compute_hiring_intent_evidence(p, org) if org else {}

            items.append({
                "id": p.id,
                "title": p.title,
                "primary_segment": p.primary_segment,
                "scope_level": p.scope_level,
                "work_type": p.work_type,
                "budget_min": p.budget_min,
                "budget_max": p.budget_max,
                "currency": p.currency,
                "rate_period": p.rate_period,
                "budget_basis_notes": p.budget_basis_notes,
                "hiring_deadline": p.hiring_deadline.isoformat(),
                "skills_required": p.skills_required,
                "acceptance_criteria": p.acceptance_criteria,
                "hiring_intent_evidence": intent,
                "created_at": p.created_at.isoformat(),
            })
        return {"projects": items, "count": len(items)}


@router.get("/{project_id}")
async def get_project_details(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    project = await service.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Determine if viewer is org member
    is_client_owner = False
    try:
        await service.verify_client_access(project.org_id, user.id)
        is_client_owner = True
    except (PermissionError, Exception):
        is_client_owner = False

    # Freelancer can only view if project is approved_open or beyond, or if sample
    if not is_client_owner and project.status in {"draft", "needs_clarification"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not published to candidates",
        )

    org = await service.org_service.get_org_by_id(project.org_id)
    intent = service.compute_hiring_intent_evidence(project, org) if org else {}

    result: dict[str, Any] = {
        "id": project.id,
        "org_id": project.org_id,
        "org_name": org.name if org else "Unknown",
        "title": project.title,
        "raw_description": project.raw_description if is_client_owner else project.raw_description[:500],
        "ai_scope_summary": project.ai_scope_summary,
        "ai_clarification_approved": project.ai_clarification_approved,
        "primary_segment": project.primary_segment,
        "scope_level": project.scope_level,
        "work_type": project.work_type,
        "commitment_type": project.commitment_type,
        "required_hours_per_week": project.required_hours_per_week,
        "skills_required": project.skills_required,
        "acceptance_criteria": project.acceptance_criteria,
        "milestone_outline": project.milestone_outline,
        "budget_min": project.budget_min,
        "budget_max": project.budget_max,
        "currency": project.currency,
        "rate_period": project.rate_period,
        "budget_basis_notes": project.budget_basis_notes,
        "hiring_deadline": project.hiring_deadline.isoformat(),
        "reconfirm_by": project.reconfirm_by.isoformat() if is_client_owner else None,
        "payment_verified": project.payment_verified,
        "status": project.status,
        "review_state": project.review_state if is_client_owner else None,
        "flagged_reason": project.flagged_reason if is_client_owner else None,
        "hiring_intent_evidence": intent,
        "is_client_owner": is_client_owner,
    }

    if is_client_owner:
        result["shortlisted_candidates"] = [
            {
                "id": c.id,
                "candidate_id": c.candidate_id,
                "stage": c.stage,
                "notes": c.notes,
                "created_at": c.created_at.isoformat(),
            }
            for c in project.shortlisted_candidates
        ]
        result["status_history"] = [
            {
                "id": h.id,
                "from_status": h.from_status,
                "to_status": h.to_status,
                "action": h.action,
                "actor_id": h.actor_id,
                "reason": h.reason,
                "created_at": h.created_at.isoformat(),
            }
            for h in project.status_history
        ]

    return {"project": result}


@router.put("/{project_id}/ai-scope/approve")
async def approve_ai_scope(
    project_id: str,
    payload: ApproveScopePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    try:
        project = await service.approve_ai_scope_clarification(
            project_id=project_id,
            actor_id=user.id,
            custom_summary=payload.custom_summary,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "AI scope approved", "ai_clarification_approved": project.ai_clarification_approved}


@router.post("/{project_id}/submit")
async def submit_project(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    try:
        project = await service.submit_project(project_id, user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "message": (
            "Project submitted for review; flagged by safety scanner for human review."
            if project.review_state == "flagged_for_human_review"
            else "Project published and open for candidates."
        ),
        "status": project.status,
        "review_state": project.review_state,
        "flagged_reason": project.flagged_reason,
    }


@router.post("/{project_id}/transition")
async def transition_project(
    project_id: str,
    payload: TransitionPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    try:
        project = await service.transition_project_status(
            project_id=project_id,
            actor_id=user.id,
            target_status=payload.target_status,
            reason=payload.reason,
            metadata=payload.metadata,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": f"Project transitioned to {project.status}", "status": project.status}


@router.post("/{project_id}/reconfirm")
async def reconfirm_project(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    try:
        project = await service.reconfirm_project(project_id, user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Hiring intent reconfirmed", "reconfirm_by": project.reconfirm_by.isoformat()}


@router.post("/{project_id}/shortlist")
async def shortlist_candidate(
    project_id: str,
    payload: ShortlistPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    try:
        item = await service.shortlist_candidate(
            project_id=project_id,
            actor_id=user.id,
            candidate_id=payload.candidate_id,
            notes=payload.notes,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Candidate shortlisted", "shortlist_id": item.id, "stage": item.stage}


@router.put("/{project_id}/shortlist/{candidate_id}")
async def update_candidate_stage(
    project_id: str,
    candidate_id: str,
    payload: CandidateStagePayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ProjectService(session)
    try:
        item = await service.update_candidate_stage(
            project_id=project_id,
            actor_id=user.id,
            candidate_id=candidate_id,
            new_stage=payload.stage,
            notes=payload.notes,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Candidate stage updated", "stage": item.stage}


# -------------------------------------------------------------------------
# Clarifications Endpoints
# -------------------------------------------------------------------------


@router.post("/{project_id}/clarifications")
async def submit_clarification_question(
    project_id: str,
    payload: ClarificationQuestionPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ClarificationService(session)
    try:
        req = await service.submit_question(
            project_id=project_id,
            freelancer_id=user.id,
            question=payload.question,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Clarification question submitted", "clarification_id": req.id}


@router.post("/clarifications/{clarification_id}/answer")
async def answer_clarification_question(
    clarification_id: str,
    payload: ClarificationAnswerPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ClarificationService(session)
    try:
        req = await service.answer_question(
            clarification_id=clarification_id,
            client_actor_id=user.id,
            answer=payload.answer,
            is_public=payload.is_public,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Clarification answered", "status": req.status}


@router.get("/{project_id}/clarifications")
async def list_project_clarifications(
    project_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    include_pending: bool = Query(default=False),
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ClarificationService(session)
    items = await service.get_project_clarifications(project_id, include_pending=include_pending)
    return {"clarifications": items}


# -------------------------------------------------------------------------
# Moderation & Appeal Queue Endpoints
# -------------------------------------------------------------------------


@router.post("/{project_id}/appeal")
async def appeal_project(
    project_id: str,
    payload: AppealPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    _enforce_marketplace_access(user)
    service = ModerationService(session)
    try:
        entry = await service.appeal_flagged_project(
            project_id=project_id,
            actor_id=user.id,
            appeal_details=payload.appeal_details,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Appeal submitted for human reviewer resolution", "queue_id": entry.id}


@router.get("/moderation/queue")
async def list_moderation_queue(
    superuser: Annotated[User, Depends(require_roles("marketplace_moderator"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    service = ModerationService(session)
    entries = await service.list_pending_queue(limit=limit)
    return {"queue": entries}


@router.post("/moderation/{queue_id}/resolve")
async def resolve_moderation(
    queue_id: str,
    payload: ModerationDecisionPayload,
    superuser: Annotated[User, Depends(require_roles("marketplace_moderator"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = ModerationService(session)
    try:
        entry = await service.resolve_moderation_entry(
            queue_id=queue_id,
            reviewer_id=superuser.id,
            decision=payload.decision,
            reviewer_notes=payload.reviewer_notes,
            commit=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    session.add(AuditEvent(action="native_project_moderation_resolved", user_id=superuser.id, meta={
        "queue_id": queue_id, "decision": payload.decision, "reason": payload.reviewer_notes[:500],
    }))
    await session.commit()

    return {"message": f"Moderation resolved as {entry.status}", "status": entry.status}


@router.post("/maintenance/expire-stale")
async def expire_stale_projects_task(
    superuser: Annotated[User, Depends(get_current_active_superuser)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = ProjectService(session)
    expired_count = await service.expire_stale_projects()
    return {"message": f"Expired {expired_count} stale projects", "count": expired_count}
