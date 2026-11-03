from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from app.api.dependencies import get_current_user
from app.schemas.user import UserRead
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.email_service import EmailService
from backend.application.services.user_service import UserService
from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from database.core.session import get_db
from database.models.application import JobApplication
from database.models.lead_action import UserLeadAction
from database.models.notification import NotificationRecord
from database.models.preference import UserPreferences
from database.models.user import User
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/me/export")
async def export_current_user_data(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """GDPR Article 20 Data Portability: exports all account, preference, lead action, and draft history as structured JSON."""
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "plan": current_user.plan,
        "subscription_status": current_user.subscription_status,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }

    pref_res = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    pref = pref_res.scalar_one_or_none()
    preferences_data: dict[str, Any] | None = None
    if pref:
        preferences_data = {
            "keywords": pref.keywords,
            "exclude_keywords": pref.exclude_keywords,
            "skills": pref.skills,
            "experience_level": pref.experience_level,
            "min_budget": pref.min_budget,
            "max_budget": pref.max_budget,
            "min_hourly_rate": pref.min_hourly_rate,
            "sources": pref.sources,
            "match_threshold": pref.match_threshold,
            "notification_channels": pref.notification_channels,
            "digest_mode": pref.digest_mode,
            "freelance_focus": pref.freelance_focus,
            "location": pref.location,
            "timezone": pref.timezone,
            "digest_days": pref.digest_days,
            "digest_time_local": pref.digest_time_local,
            "destinations": pref.destinations,
        }

    actions_res = await session.execute(
        select(UserLeadAction).where(UserLeadAction.user_id == current_user.id)
    )
    lead_actions = [
        {
            "job_id": a.job_id,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in actions_res.scalars().all()
    ]

    apps_res = await session.execute(
        select(JobApplication).where(JobApplication.user_id == current_user.id)
    )
    applications = [
        {
            "id": app.id,
            "job_id": app.job_id,
            "source_name": app.source_name,
            "status": app.status,
            "proposal": app.proposal,
            "bid_amount": app.bid_amount,
            "created_at": app.created_at.isoformat() if app.created_at else None,
        }
        for app in apps_res.scalars().all()
    ]

    notifs_res = await session.execute(
        select(NotificationRecord).where(NotificationRecord.user_id == current_user.id)
    )
    notifications = [
        {
            "public_id": n.public_id,
            "title": n.title,
            "body": n.body,
            "channels": n.channels,
            "status": n.status,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs_res.scalars().all()
    ]

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "user": user_data,
        "preferences": preferences_data,
        "lead_actions": lead_actions,
        "applications": applications,
        "notifications": notifications,
    }


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    EmailService.send_account_alert(
        current_user.email,
        "Your Signal Desk account was deleted",
        "We deleted your account and the preferences tied to it. This mailbox will not receive job alerts anymore.",
    )
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    await service.delete_user(current_user)
