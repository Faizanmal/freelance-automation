"""Phase 08 — Lead pipeline CRM API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from app.api.dependencies import get_current_user
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import productivity_entitlements
from backend.application.services.pipeline import PipelineService
from database.core.session import get_db
from database.models.crm import PIPELINE_STAGES
from database.models.job import JobRecord
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Query, Response

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

StageLiteral = Literal[
    "discovered",
    "saved",
    "researching",
    "ready",
    "applied",
    "interview",
    "negotiating",
    "won",
    "lost",
    "archived",
]


class StagePayload(BaseModel):
    stage: StageLiteral
    reason: str | None = Field(default=None, max_length=128)
    lost_reason: str | None = Field(default=None, max_length=256)
    won_value: float | None = None
    confirm_applied: bool = False


class LeadUpdatePayload(BaseModel):
    follow_up_at: datetime | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    employer_name: str | None = Field(default=None, max_length=256)
    contact_name: str | None = Field(default=None, max_length=256)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_url: str | None = Field(default=None, max_length=1024)
    contact_notes: str | None = Field(default=None, max_length=2000)
    won_value: float | None = None
    lost_reason: str | None = Field(default=None, max_length=256)
    time_spent_seconds: int | None = Field(default=None, ge=0, le=86400 * 30)


class BulkStagePayload(BaseModel):
    job_ids: list[int] = Field(min_length=1, max_length=50)
    stage: StageLiteral
    reason: str | None = Field(default=None, max_length=128)


class NotePayload(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    kind: Literal["note", "negotiation", "research"] = "note"


class TaskPayload(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    due_at: datetime | None = None


class ReminderPayload(BaseModel):
    remind_at: datetime
    message: str | None = Field(default=None, max_length=512)
    kind: str = Field(default="follow_up", max_length=32)


@router.get("/stages")
async def list_stages(
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "stages": list(PIPELINE_STAGES),
        "entitlements": productivity_entitlements(user),
        "single_user": True,
        "outward_automation": False,
    }


@router.get("/leads")
async def list_pipeline_leads(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    stage: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    follow_up_due: bool = False,
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    service = PipelineService(db)
    result = await service.list_leads(
        user_id=user.id,
        stage=stage,
        q=q,
        tag=tag,
        follow_up_due=follow_up_due,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    await db.commit()
    return result


@router.get("/board")
async def pipeline_board(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.api.v1.preferences import _archive_noise_lead_actions

    await _archive_noise_lead_actions(db, user.id)
    service = PipelineService(db)
    result = await service.board(user_id=user.id)
    await db.commit()
    return result


@router.get("/dashboard")
async def workspace_dashboard(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    demo: bool = False,
) -> dict[str, Any]:
    from app.api.v1.preferences import _archive_noise_lead_actions

    if not demo:
        await _archive_noise_lead_actions(db, user.id)
    service = PipelineService(db)
    return await service.workspace_dashboard(user_id=user.id, demo=demo)


@router.put("/leads/{job_id}/stage")
async def set_lead_stage(
    job_id: int,
    payload: StagePayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    job = (
        await db.execute(select(JobRecord).where(JobRecord.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    service = PipelineService(db)
    try:
        row = await service.set_stage(
            user_id=user.id,
            job_id=job_id,
            stage=payload.stage,
            reason=payload.reason,
            lost_reason=payload.lost_reason,
            won_value=payload.won_value,
            confirm_applied=payload.confirm_applied,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(row)
    return {"lead": serialize_with_job(row, job)}


@router.patch("/leads/{job_id}")
async def update_lead(
    job_id: int,
    payload: LeadUpdatePayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    fields = payload.model_dump(exclude_unset=True)
    try:
        row = await service.update_lead(user_id=user.id, job_id=job_id, **fields)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job = (
        await db.execute(select(JobRecord).where(JobRecord.id == job_id))
    ).scalar_one_or_none()
    await db.commit()
    await db.refresh(row)
    return {"lead": serialize_with_job(row, job)}


@router.delete("/leads/{job_id}")
async def delete_lead(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    service = PipelineService(db)
    try:
        await service.soft_delete(user_id=user.id, job_id=job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return {"status": "deleted"}


@router.post("/leads/bulk-stage")
async def bulk_stage(
    payload: BulkStagePayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    try:
        result = await service.bulk_set_stage(
            user_id=user.id,
            job_ids=payload.job_ids,
            stage=payload.stage,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return result


@router.post("/undo/{undo_id}")
async def undo_action(
    undo_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    try:
        result = await service.undo(user_id=user.id, undo_id=undo_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return result


@router.get("/leads/{job_id}/history")
async def lead_history(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    events = await service.stage_history(user_id=user.id, job_id=job_id)
    return {"events": events}


@router.post("/leads/{job_id}/notes")
async def add_note(
    job_id: int,
    payload: NotePayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    note = await service.add_note(
        user_id=user.id, job_id=job_id, body=payload.body, kind=payload.kind
    )
    await db.commit()
    await db.refresh(note)
    return {
        "note": {
            "id": note.id,
            "body": note.body,
            "kind": note.kind,
            "created_at": note.created_at.isoformat() if note.created_at else None,
        }
    }


@router.get("/leads/{job_id}/notes")
async def list_notes(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    notes = await service.list_notes(user_id=user.id, job_id=job_id)
    return {
        "notes": [
            {
                "id": n.id,
                "body": n.body,
                "kind": n.kind,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notes
        ]
    }


@router.post("/leads/{job_id}/tasks")
async def add_task(
    job_id: int,
    payload: TaskPayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    task = await service.add_task(
        user_id=user.id,
        job_id=job_id,
        title=payload.title,
        due_at=payload.due_at,
    )
    await db.commit()
    await db.refresh(task)
    return {
        "task": {
            "id": task.id,
            "title": task.title,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "completed_at": None,
        }
    }


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    try:
        task = await service.complete_task(user_id=user.id, task_id=task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return {
        "task": {
            "id": task.id,
            "title": task.title,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
    }


@router.post("/leads/{job_id}/reminders")
async def add_reminder(
    job_id: int,
    payload: ReminderPayload,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    reminder = await service.add_reminder(
        user_id=user.id,
        job_id=job_id,
        remind_at=payload.remind_at,
        message=payload.message,
        kind=payload.kind,
    )
    await db.commit()
    await db.refresh(reminder)
    return {
        "reminder": {
            "id": reminder.id,
            "remind_at": reminder.remind_at.isoformat(),
            "message": reminder.message,
            "kind": reminder.kind,
            "duplicate_suppressed": False,
        }
    }


@router.post("/reminders/{reminder_id}/cancel")
async def cancel_reminder(
    reminder_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    service = PipelineService(db)
    try:
        reminder = await service.cancel_reminder(
            user_id=user.id, reminder_id=reminder_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return {
        "reminder": {
            "id": reminder.id,
            "cancelled_at": reminder.cancelled_at.isoformat()
            if reminder.cancelled_at
            else None,
        }
    }


@router.get("/export.csv")
async def export_csv(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    service = PipelineService(db)
    content = await service.export_csv(user_id=user.id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pipeline-export.csv"},
    )


@router.get("/export.ics")
async def export_ics(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    service = PipelineService(db)
    content = await service.export_ics_tasks(user_id=user.id)
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=pipeline-followups.ics"},
    )


def serialize_with_job(row, job) -> dict[str, Any]:
    from backend.application.services.pipeline import serialize_lead

    return serialize_lead(row, job)
