"""Phase 08 — Typed AI copilot + durable agent runs API."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from app.api.dependencies import get_current_user
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import productivity_entitlements
from backend.application.services.copilot import CopilotService
from database.core.session import get_db
from database.models.crm import COPILOT_INTENTS
from database.models.job import JobRecord
from database.models.preference import UserPreferences
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/copilot", tags=["copilot"])

IntentLiteral = Literal[
    "lead_brief",
    "requirements_gap",
    "portfolio_selection",
    "proposal_draft",
    "interview_prep",
    "scope_clarification",
    "negotiation_scenario",
]


class StartRunPayload(BaseModel):
    job_id: int
    intent: IntentLiteral
    idempotency_key: str | None = Field(default=None, max_length=128)
    timeout_seconds: int = Field(default=60, ge=5, le=120)
    # Explicit confirmation required for any future side-effect dispatch.
    # Copilot never auto-sends; this flag is reserved for preview→dispatch gates.
    confirm_side_effect: bool = False


class DraftUpdatePayload(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    title: str | None = Field(default=None, max_length=256)


@router.get("/intents")
async def list_intents(
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "intents": list(COPILOT_INTENTS),
        "entitlements": productivity_entitlements(user),
        "never_auto_sends": True,
        "allowlisted_tools_only": True,
    }


@router.post("/runs")
async def start_run(
    payload: StartRunPayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    if payload.confirm_side_effect:
        # Hard block: no outward message/application from copilot, even with confirm.
        raise HTTPException(
            status_code=400,
            detail="copilot_cannot_dispatch_outward; use explicit apply/email flow",
        )

    job = (
        await db.execute(select(JobRecord).where(JobRecord.id == payload.job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    prefs = (
        await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user.id)
        )
    ).scalar_one_or_none()
    if prefs is None:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
        await db.flush()

    service = CopilotService(db)
    try:
        result = await service.start_run(
            user=user,
            job=job,
            preferences=prefs,
            intent=payload.intent,
            idempotency_key=payload.idempotency_key,
            timeout_seconds=payload.timeout_seconds,
            confirm_side_effect=False,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()
    result["audit_receipt"] = {
        "action": "copilot_run",
        "run_id": result["id"],
        "auto_sent": False,
        "listing_url": job.url,
    }
    return result


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = CopilotService(db)
    try:
        return await service.get_run(user_id=user.id, run_id=run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = CopilotService(db)
    try:
        result = await service.cancel_run(user_id=user.id, run_id=run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return result


@router.post("/runs/{run_id}/retry")
async def retry_run(
    run_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    prefs = (
        await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user.id)
        )
    ).scalar_one_or_none()
    if prefs is None:
        raise HTTPException(status_code=400, detail="preferences_required")

    service = CopilotService(db)
    try:
        result = await service.retry_run(
            user=user, preferences=prefs, run_id=run_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    await db.commit()
    return result


@router.get("/drafts")
async def list_drafts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    job_id: int | None = None,
) -> dict[str, Any]:
    service = CopilotService(db)
    drafts = await service.list_drafts(user_id=user.id, job_id=job_id)
    return {"drafts": drafts, "never_auto_sends": True}


@router.patch("/drafts/{draft_id}")
async def update_draft(
    draft_id: int,
    payload: DraftUpdatePayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = CopilotService(db)
    try:
        draft = await service.update_draft(
            user_id=user.id,
            draft_id=draft_id,
            body=payload.body,
            title=payload.title,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return {"draft": draft}
