from __future__ import annotations

from typing import Annotated, Any

from app.api.dependencies import get_current_active_superuser
from app.schemas.user import UserRead
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core.session import get_db
from database.models.job import JobRecord
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])


class UserAdminUpdate(BaseModel):
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_verified: bool | None = None
    plan: str | None = None


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
