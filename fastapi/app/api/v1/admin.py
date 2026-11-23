from __future__ import annotations

from typing import Annotated, Any

from app.api.dependencies import get_current_active_superuser, require_roles
from app.schemas.user import UserRead
from backend.application.services.trust.listing_reports import sanitize_report_text
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core.session import get_db
from database.models.job import JobRecord
from database.models.audit import AuditEvent
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])


class UserAdminUpdate(BaseModel):
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_verified: bool | None = None
    plan: str | None = None
    reason: str | None = Field(default=None, min_length=10, max_length=500)

    @model_validator(mode="after")
    def require_reason_for_privileged_changes(self):
        if any(getattr(self, key) is not None for key in ("is_active", "is_superuser", "is_verified")) and not self.reason:
            raise ValueError("A reason is required for account restriction or verification changes")
        return self


@router.get("/users", response_model=list[UserRead])
async def list_users(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    session: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> list[UserRead]:
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return [UserRead.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    user_in: UserAdminUpdate,
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser
    if user_in.is_verified is not None:
        user.is_verified = user_in.is_verified
    if user_in.plan is not None:
        norm_plan = user_in.plan.strip().lower()
        user.plan = norm_plan
        # Keep subscription_status in sync so is_pro(user) works seamlessly
        if norm_plan == "pro":
            user.subscription_status = "active"
        elif norm_plan == "free":
            user.subscription_status = "inactive"

    if any(getattr(user_in, key) is not None for key in ("is_active", "is_superuser", "is_verified")):
        if user.id == current_user.id and (user_in.is_active is False or user_in.is_superuser is False):
            raise HTTPException(status_code=400, detail="You cannot remove your own access")
        session.add(AuditEvent(action="admin_account_updated", user_id=current_user.id, meta={
            "target_user_id": user.id,
            "changes": {key: getattr(user_in, key) for key in ("is_active", "is_superuser", "is_verified") if getattr(user_in, key) is not None},
            "reason": sanitize_report_text(user_in.reason, limit=400),
        }))

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserRead.model_validate(user)


@router.get("/telemetry/system")
async def get_system_telemetry(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    # Jobs breakdown by source
    source_res = await session.execute(
        select(JobRecord.source_name, func.count(JobRecord.id))
        .group_by(JobRecord.source_name)
    )
    jobs_by_source = {row[0]: row[1] for row in source_res.all() if row[0]}

    total_jobs = sum(jobs_by_source.values())
    expired_res = await session.execute(
        select(func.count(JobRecord.id)).where(JobRecord.is_expired.is_(True))
    )
    total_expired = expired_res.scalar() or 0

    # User stats
    total_users_res = await session.execute(select(func.count(User.id)))
    total_users = total_users_res.scalar() or 0

    pro_users_res = await session.execute(
        select(func.count(User.id)).where(User.plan == "pro")
    )
    pro_users = pro_users_res.scalar() or 0

    return {
        "total_jobs": total_jobs,
        "active_jobs": max(0, total_jobs - total_expired),
        "expired_jobs": total_expired,
        "jobs_by_source": jobs_by_source,
        "total_users": total_users,
        "pro_users": pro_users,
    }


@router.post("/trigger-sweep")
async def trigger_stale_sweep(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from backend.application.services.job_expiration import JobExpirationService

    service = JobExpirationService(session)
    expired = await service.sweep_stale_jobs(max_stale_days=45, limit=200)
    return {"status": "ok", "expired_count": expired}


class SourceDisableRequest(BaseModel):
    disabled: bool = True
    reason: str = Field(min_length=10, max_length=500)


@router.get("/sources")
async def list_source_policies(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
) -> dict[str, Any]:
    from app.ingestion.governance import governance_audit_summary, list_policies
    from app.ingestion.reliability import get_spend_today, list_quarantine

    policies = [p.to_dict() for p in list_policies(include_disabled=True)]
    return {
        "sources": policies,
        "audit": governance_audit_summary(),
        "spend_today_usd": await get_spend_today(),
        "quarantine_open": len(await list_quarantine(limit=500)),
    }


@router.get("/sources/health")
async def source_health(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
) -> dict[str, Any]:
    from app.ingestion.governance import list_policies
    from app.ingestion.reliability import circuit_is_open, get_spend_today

    rows = []
    for policy in list_policies(include_disabled=True):
        rows.append(
            {
                **policy.to_dict(),
                "circuit_open": await circuit_is_open(policy.key),
            }
        )
    return {"sources": rows, "spend_today_usd": await get_spend_today()}


@router.get("/sources/quarantine")
async def source_quarantine(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    limit: int = 50,
) -> dict[str, Any]:
    from app.ingestion.reliability import list_quarantine

    items = await list_quarantine(limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/sources/{source_key}/disable")
async def disable_source(
    source_key: str,
    body: SourceDisableRequest,
    current_user: Annotated[User, Depends(require_roles("source_operator"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.ingestion.governance import get_typed_registry, set_operator_disabled
    from app.ingestion.sources import SOURCE_REGISTRY

    if source_key not in SOURCE_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown source")
    safe_reason = sanitize_report_text(body.reason, limit=400) or "Operator source policy change"
    session.add(AuditEvent(action="source_operator_disabled" if body.disabled else "source_operator_enabled",
                           user_id=current_user.id, meta={"source_key": source_key, "reason": safe_reason}))
    await session.commit()
    set_operator_disabled(source_key, body.disabled)
    policy = get_typed_registry().get(source_key)
    return {
        "status": "ok",
        "source": source_key,
        "operator_disabled": body.disabled,
        "policy": policy.to_dict() if policy else None,
    }


@router.get("/inventory/quality")
async def inventory_quality(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 500,
) -> dict[str, Any]:
    from app.ingestion.normalize import inventory_quality_stats
    from app.ingestion.sources import SOURCE_ATTRIBUTION

    result = await session.execute(
        select(JobRecord).order_by(JobRecord.created_at.desc()).limit(limit)
    )
    jobs = result.scalars().all()
    rows = [
        {
            "url": j.url,
            "company": j.company,
            "work_type": getattr(j, "work_type", None),
            "is_expired": bool(getattr(j, "is_expired", False)),
            "state": getattr(j, "inventory_state", None),
            "source_name": j.source_name,
        }
        for j in jobs
    ]
    stats = inventory_quality_stats(rows)
    by_source = await session.execute(
        select(JobRecord.source_name, func.count(JobRecord.id)).group_by(
            JobRecord.source_name
        )
    )
    coverage = {
        name: {
            "count": count,
            "attribution": SOURCE_ATTRIBUTION.get(name, name),
        }
        for name, count in by_source.all()
        if name
    }
    return {"quality": stats, "coverage": coverage, "sample_size": len(rows)}


@router.get("/hunt-runs/status")
async def hunt_run_status(
    current_user: Annotated[User, Depends(get_current_active_superuser)],
) -> dict[str, Any]:
    """Read model for last hunt / source gate state (ops console)."""
    from app.ingestion.governance import governance_audit_summary, list_policies
    from app.ingestion.reliability import get_spend_today, list_quarantine

    return {
        "audit": governance_audit_summary(),
        "enabled_sources": [
            p.key
            for p in list_policies(include_disabled=False)
            if not p.operator_disabled
        ],
        "spend_today_usd": await get_spend_today(),
        "quarantine": await list_quarantine(limit=20),
        "note": (
            "Discovery ingestion is shared inventory. User ranking and digest "
            "scheduling are separate."
        ),
    }
