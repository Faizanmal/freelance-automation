from __future__ import annotations

from app.api.dependencies import get_current_user
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import (
    destinations_from_preferences,
    filter_channels_for_user,
    is_pro,
)
from backend.application.services.notification_service import (
    NotificationAction,
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationService,
)
from backend.application.services.persistent_notifications import (
    PersistentNotificationService,
)
from database.core.session import get_db
from database.models.notification import NotificationDelivery, NotificationRecord
from database.models.preference import UserPreferences
from database.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/notifications", tags=["notifications"])
legacy_service = NotificationService()


class NotificationRequest(BaseModel):
    title: str
    body: str
    channels: list[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.EMAIL])
    priority: NotificationPriority = NotificationPriority.NORMAL
    digest: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    ai_summary: str | None = None
    actions: list[NotificationAction] = Field(default_factory=list)
    job_id: int | None = None


class DigestRequest(BaseModel):
    items: list[NotificationRequest]


async def _load_destinations(session: AsyncSession, user: User) -> dict[str, str]:
    result = await session.execute(select(UserPreferences).where(UserPreferences.user_id == user.id))
    prefs = result.scalar_one_or_none()
    if prefs is None:
        return {"email": user.email}
    destinations = destinations_from_preferences(prefs)
    if "email" not in destinations:
        destinations["email"] = prefs.alert_email or user.email
    return destinations


@router.post("/send")
async def send_notification(
    payload: NotificationRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, object]:
    quiet_start = None
    quiet_end = None
    if payload.quiet_hours_start:
        quiet_start = __import__("datetime").datetime.strptime(payload.quiet_hours_start, "%H:%M").time()
    if payload.quiet_hours_end:
        quiet_end = __import__("datetime").datetime.strptime(payload.quiet_hours_end, "%H:%M").time()

    channel_names = filter_channels_for_user(current_user, [channel.value for channel in payload.channels])
    if not channel_names:
        raise HTTPException(status_code=400, detail="No allowed channels for your plan")
    if not is_pro(current_user) and set(channel_names) - {"email"}:
        raise HTTPException(status_code=402, detail="Multi-channel alerts require Pro")

    channels = [NotificationChannel(name) for name in channel_names]
    destinations = await _load_destinations(session, current_user)
    envelope = NotificationPayload(
        user_id=str(current_user.id),
        title=payload.title,
        body=payload.body,
        channels=channels,
        priority=payload.priority,
        digest=payload.digest,
        quiet_hours_start=quiet_start,
        quiet_hours_end=quiet_end,
        ai_summary=payload.ai_summary or legacy_service.build_ai_summary(payload.title, payload.body),
        actions=payload.actions,
        destinations=destinations,
    )
    persistent = PersistentNotificationService(session)
    result = await persistent.send(envelope, job_id=payload.job_id)
    return {"status": result["status"], **result}


@router.post("/digest")
async def send_digest(
    payload: DigestRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, object]:
    if not payload.items:
        raise HTTPException(status_code=400, detail="At least one item is required")
    destinations = await _load_destinations(session, current_user)
    digest = legacy_service.build_digest(
        [
            NotificationPayload(
                user_id=str(current_user.id),
                title=item.title,
                body=item.body,
                channels=item.channels,
                priority=item.priority,
                digest=item.digest,
                ai_summary=item.ai_summary,
                actions=item.actions,
                destinations=destinations,
            )
            for item in payload.items
        ]
    )
    persistent = PersistentNotificationService(session)
    result = await persistent.send(digest)
    return {"status": result["status"], "digest_title": digest.title, **result}


@router.get("/history")
async def notification_history(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, object]:
    user_id = str(current_user.id)
    result = await session.execute(
        select(NotificationRecord)
        .where(NotificationRecord.user_id == user_id)
        .order_by(desc(NotificationRecord.created_at))
        .limit(limit)
    )
    records = list(result.scalars().all())
    items = []
    for record in records:
        deliveries = await session.execute(
            select(NotificationDelivery).where(NotificationDelivery.notification_id == record.id)
        )
        items.append(
            {
                "id": record.id,
                "public_id": record.public_id,
                "user_id": record.user_id,
                "title": record.title,
                "body": record.body,
                "channels": record.channels,
                "priority": record.priority,
                "status": record.status,
                "job_id": record.job_id,
                "ai_summary": record.ai_summary,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "deliveries": [
                    {
                        "channel": delivery.channel,
                        "delivered": delivery.delivered,
                        "message_id": delivery.message_id,
                        "error": delivery.error,
                    }
                    for delivery in deliveries.scalars().all()
                ],
            }
        )
    return {"items": items}


@router.get("/retry-queue")
async def retry_queue(_current_user: User = Depends(get_current_user)) -> dict[str, object]:  # noqa: B008
    return {"items": [entry.__dict__ for entry in legacy_service.get_retry_queue()]}
