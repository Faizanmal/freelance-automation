from __future__ import annotations

from pydantic import BaseModel, Field

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from app.api.dependencies import get_current_user, require_roles
from app.schemas.user import UserRead
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.audit import record_audit
from backend.application.services.email_service import EmailService
from backend.application.services.user_service import UserService
from backend.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from config.settings import get_settings
from database.core.session import get_db
from database.models.application import JobApplication
from database.models.audit import AuditEvent, UserConsent
from database.models.lead_action import UserLeadAction
from database.models.notification import NotificationRecord
from database.models.preference import UserPreferences
from database.models.user import User
from fastapi import APIRouter, Depends, Request, status

router = APIRouter(prefix="/users", tags=["users"])

ALLOWED_ROLES = frozenset({"freelancer", "client", "staff"})
ALLOWED_VISIBILITY = frozenset({"private", "public"})


class UserUpdatePayload(BaseModel):
    full_name: str | None = Field(None, max_length=120)
    account_role: str | None = Field(None, max_length=32)
    profile_visibility: str | None = Field(None, max_length=32)


class ConsentPayload(BaseModel):
    purpose: str = Field(min_length=2, max_length=64)
    granted: bool
    source: str | None = Field(None, max_length=64)


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    payload: UserUpdatePayload,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    changed = False
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip() or None
        changed = True
    if payload.account_role is not None:
        role = payload.account_role.strip().lower()
        if role not in ALLOWED_ROLES:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Invalid account_role")
        # Staff elevation is server-gated — only superusers may self-assign staff.
        if role == "staff" and not current_user.is_superuser:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403, detail="Staff role requires administrator elevation"
            )
        current_user.account_role = role
        changed = True
    if payload.profile_visibility is not None:
        vis = payload.profile_visibility.strip().lower()
        if vis not in ALLOWED_VISIBILITY:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Invalid profile_visibility")
        current_user.profile_visibility = vis
        changed = True
    if changed:
        session.add(current_user)
        await session.commit()
        await session.refresh(current_user)
    return UserRead.model_validate(current_user)


@router.get("/me/export")
async def export_current_user_data(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """GDPR Article 20 Data Portability: exports all account, preference, lead action, and draft history as structured JSON."""
    await record_audit(
        session,
        action="privacy.export",
        user_id=str(current_user.id),
        actor_ip=request.client.host if request.client else None,
    )
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "plan": current_user.plan,
        "subscription_status": current_user.subscription_status,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "account_role": getattr(current_user, "account_role", "freelancer"),
        "profile_visibility": getattr(current_user, "profile_visibility", "private"),
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

    consents_res = await session.execute(
        select(UserConsent).where(UserConsent.user_id == current_user.id)
    )
    consents = [
        {
            "purpose": c.purpose,
            "granted": c.granted,
            "source": c.source,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in consents_res.scalars().all()
    ]

    await session.commit()
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "user": user_data,
        "preferences": preferences_data,
        "lead_actions": lead_actions,
        "applications": applications,
        "notifications": notifications,
        "consents": consents,
        "retention_note": (
            "Operational logs rotate on a routine schedule. Account deletion removes "
            "profile, preferences, lead actions, and applications. Legal holds may delay purge."
        ),
    }


@router.get("/me/consents")
async def list_consents(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    res = await session.execute(
        select(UserConsent).where(UserConsent.user_id == current_user.id)
    )
    items = [
        {
            "purpose": c.purpose,
            "granted": c.granted,
            "source": c.source,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in res.scalars().all()
    ]
    return {"items": items}


@router.put("/me/consents")
async def upsert_consent(
    payload: ConsentPayload,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    purpose = payload.purpose.strip().lower()
    res = await session.execute(
        select(UserConsent).where(
            UserConsent.user_id == current_user.id,
            UserConsent.purpose == purpose,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = UserConsent(
            id=str(uuid4()),
            user_id=current_user.id,
            purpose=purpose,
            granted=payload.granted,
            source=payload.source or "privacy_center",
        )
        session.add(row)
    else:
        row.granted = payload.granted
        row.source = payload.source or row.source or "privacy_center"
        session.add(row)
    await record_audit(
        session,
        action="privacy.consent",
        user_id=str(current_user.id),
        actor_ip=request.client.host if request.client else None,
        meta={"purpose": purpose, "granted": payload.granted},
    )
    await session.commit()
    return {"purpose": purpose, "granted": payload.granted}


@router.get("/me/audit")
async def list_my_audit(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Recent sensitive operations for the signed-in user (no secrets)."""
    res = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.user_id == current_user.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(50)
    )
    items = [
        {
            "action": e.action,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "meta": e.meta,
        }
        for e in res.scalars().all()
    ]
    return {"items": items}


@router.get("/me/profile-completeness")
async def profile_completeness(
    current_user: Annotated[User, Depends(require_roles("freelancer", "client", "staff"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    pref_res = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    pref = pref_res.scalar_one_or_none()
    checks = {
        "verified_email": bool(current_user.is_verified),
        "full_name": bool(current_user.full_name),
        "skills": bool(pref and (pref.skills or pref.keywords)),
        "rate_or_budget": bool(
            pref
            and (
                pref.min_hourly_rate is not None
                or pref.min_budget is not None
                or pref.max_budget is not None
            )
        ),
        "digest_or_alerts": bool(
            pref
            and (pref.digest_mode or (pref.notification_channels or []))
        ),
        "private_by_default": getattr(current_user, "profile_visibility", "private")
        == "private",
    }
    score = round(100 * sum(1 for v in checks.values() if v) / max(len(checks), 1))
    return {"score": score, "checks": checks}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    settings = get_settings()
    await record_audit(
        session,
        action="privacy.delete_request",
        user_id=str(current_user.id),
        actor_ip=request.client.host if request.client else None,
    )
    await session.commit()

    if settings.stripe_enabled and current_user.stripe_subscription_id:
        try:
            import stripe

            stripe.api_key = settings.stripe_secret_key
            stripe.Subscription.cancel(current_user.stripe_subscription_id)
        except Exception:
            pass

    EmailService.send_account_alert(
        current_user.email,
        "Your Signal Desk account was deleted",
        "We deleted your account and the preferences tied to it. This mailbox will not receive job alerts anymore.",
    )
    repository = SQLAlchemyUserRepository(session)
    service = UserService(repository)
    await service.delete_user(current_user)
