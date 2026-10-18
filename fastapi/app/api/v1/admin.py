from __future__ import annotations

from typing import Annotated

from app.api.dependencies import get_current_active_superuser
from app.schemas.user import UserRead
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core.session import get_db
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
        user.plan = user_in.plan

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserRead.model_validate(user)
