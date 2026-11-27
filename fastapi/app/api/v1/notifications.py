from __future__ import annotations

import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from app.api.dependencies import get_current_user
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.billing import (
    destinations_from_preferences,
    filter_channels_for_user,
    is_pro,
)
from backend.application.services.digest_scheduler import calculate_next_send
from backend.application.services.digest_service import DigestService
from backend.application.services.notification_service import (
    NotificationAction,
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationService,
)
from backend.application.services.outbox_service import OutboxService
from backend.application.services.persistent_notifications import (
    PersistentNotificationService,
)
from database.core.session import get_db
from database.models.notification import (
    NotificationDelivery,
    NotificationOutbox,
    NotificationRecord,
)
from database.models.preference import UserPreferences
from database.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])
legacy_service = NotificationService()


class NotificationRequest(BaseModel):
    title: str
    body: str
    channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.EMAIL]
    )
    priority: NotificationPriority = NotificationPriority.NORMAL
    digest: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    ai_summary: str | None = None
    actions: list[NotificationAction] = Field(default_factory=list)
    job_id: int | None = None


class DigestRequest(BaseModel):
    items: list[NotificationRequest]


class WebhookPayload(BaseModel):
    event: str
    recipient: str | None = None
    email: str | None = None
    message_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _load_user_prefs(session: AsyncSession, user: User) -> UserPreferences:
    res = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    )
    prefs = res.scalar_one_or_none()
    if prefs is None:
        prefs = UserPreferences(
            user_id=user.id,
            keywords=[],
            skills=["python", "fastapi"],
            alert_email=user.email,
            timezone="UTC",
            digest_mode=True,
        )
        session.add(prefs)
        await session.flush()
    return prefs


async def _load_destinations(session: AsyncSession, user: User) -> dict[str, str]:
    prefs = await _load_user_prefs(session, user)
    destinations = destinations_from_preferences(prefs)
    if "email" not in destinations:
        destinations["email"] = prefs.alert_email or user.email
    return destinations


# -------------------------------------------------------------------------
# Core Notification Sending & History
# -------------------------------------------------------------------------


@router.post("/send")
async def send_notification(
    payload: NotificationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    quiet_start = None
    quiet_end = None
    if payload.quiet_hours_start:
        quiet_start = (
            datetime.strptime(payload.quiet_hours_start, "%H:%M").time()
        )
    if payload.quiet_hours_end:
        quiet_end = (
            datetime.strptime(payload.quiet_hours_end, "%H:%M").time()
        )

    channel_names = filter_channels_for_user(
        current_user, [channel.value for channel in payload.channels]
    )
    if not channel_names:
        raise HTTPException(status_code=400, detail="No allowed channels for your plan")
    if not is_pro(current_user) and set(channel_names) - {"email", "in_app"}:
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
        ai_summary=payload.ai_summary
        or legacy_service.build_ai_summary(payload.title, payload.body),
        actions=payload.actions,
        destinations=destinations,
    )
    persistent = PersistentNotificationService(session)
    result = await persistent.send(envelope, job_id=payload.job_id)
    return {"status": result["status"], **result}


@router.post("/digest")
async def send_digest(
    payload: DigestRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
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
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
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
            select(NotificationDelivery).where(
                NotificationDelivery.notification_id == record.id
            )
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
                "is_read": getattr(record, "is_read", False),
                "created_at": (
                    record.created_at.isoformat() if record.created_at else None
                ),
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


# -------------------------------------------------------------------------
# In-App Inbox Endpoints
# -------------------------------------------------------------------------


@router.post("/email/test")
async def send_test_email_alert(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Send a one-off test email without creating a lead_match inbox row."""
    from backend.application.services.notification_service import (
        EmailAdapter,
        NotificationChannel,
        NotificationEnvelope,
        NotificationPriority,
    )

    destinations = await _load_destinations(session, current_user)
    to_address = destinations.get("email") or current_user.email
    if not to_address:
        raise HTTPException(status_code=400, detail="No alert email configured")

    envelope = NotificationEnvelope(
        id=f"email-test-{uuid4()}",
        user_id=str(current_user.id),
        title="Signal Desk test email",
        body=(
            "This is a test from Digest settings. If you received it, "
            "outbound email is working. This message is email-only — "
            "it does not create an in-app lead match."
        ),
        channels=[NotificationChannel.EMAIL],
        priority=NotificationPriority.NORMAL,
        digest=False,
        ai_summary="Preferences email delivery test",
        actions=[],
        destinations=destinations,
        metadata={"event_type": "test_email", "source": "preferences_test"},
    )
    result = await EmailAdapter().send(envelope)
    if not result.delivered:
        raise HTTPException(
            status_code=502,
            detail=result.error
            or "Could not deliver test email. Check RESEND_API_KEY or EMAIL_SMTP_* on the API.",
        )
    return {
        "status": "delivered",
        "delivered": True,
        "message": "Test email sent",
        "recipient": to_address,
    }


@router.post("/inbox/test")
async def create_test_inbox_alert(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Create an unread in-app inbox alert immediately (bypasses channel plan filters).

    Used by Preferences → Digest → Send test inbox alert. Always writes a durable
    NotificationRecord so /notifications shows it without waiting on email adapters.
    """
    user_id = str(current_user.id)
    # Soft rate limit: at most 5 test alerts per minute per user.
    cutoff = datetime.now(UTC) - timedelta(seconds=60)
    recent = await session.execute(
        select(func.count(NotificationRecord.id)).where(
            NotificationRecord.user_id == user_id,
            NotificationRecord.event_type == "test_inbox",
            NotificationRecord.created_at >= cutoff,
        )
    )
    if (recent.scalar() or 0) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Rate limited — wait a minute before sending another test alert",
        )

    record = NotificationRecord(
        public_id=str(uuid4()),
        user_id=user_id,
        title="Test inbox alert",
        body=(
            "Unread test alert from Preferences. Use Mark read on this item, "
            "reload, and confirm it stays under All as read."
        ),
        channels=["in_app"],
        priority="high",
        digest=False,
        ai_summary="Test alert for inbox Mark-read verification",
        status="delivered",
        job_id=None,
        metadata_json={"source": "preferences_test"},
        is_read=False,
        event_type="test_inbox",
        group_key="test_inbox",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "public_id": record.public_id,
        "status": "delivered",
        "is_read": False,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "message": "Test inbox alert sent",
    }


@router.get("/inbox")
async def get_inbox(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = Query(False),
    archived: bool = Query(False),
    event_type: str | None = Query(None),
    group_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Lists in-app inbox items with read states, grouping, and filters.

    Default (archived=false) returns active inbox including read items.
    unread_only filters to unread within the active inbox.
    archived=true returns only archived items (for restore).
    """
    user_id = str(current_user.id)
    conditions = [NotificationRecord.user_id == user_id]
    if archived:
        conditions.append(NotificationRecord.archived_at.is_not(None))
    else:
        conditions.append(NotificationRecord.archived_at.is_(None))
        if unread_only:
            conditions.append(NotificationRecord.is_read.is_(False))
    if event_type:
        conditions.append(NotificationRecord.event_type == event_type)
    if group_key:
        conditions.append(NotificationRecord.group_key == group_key)

    stmt = (
        select(NotificationRecord)
        .where(and_(*conditions))
        .order_by(desc(NotificationRecord.created_at))
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(stmt)
    records = list(res.scalars().all())

    # Calculate unread count (active inbox only)
    unread_stmt = select(func.count(NotificationRecord.id)).where(
        NotificationRecord.user_id == user_id,
        NotificationRecord.is_read.is_(False),
        NotificationRecord.archived_at.is_(None),
    )
    unread_count = (await session.execute(unread_stmt)).scalar() or 0

    return {
        "items": [
            {
                "id": r.id,
                "public_id": r.public_id,
                "title": r.title,
                "body": r.body,
                "ai_summary": r.ai_summary,
                "priority": r.priority,
                "event_type": r.event_type,
                "group_key": r.group_key,
                "job_id": r.job_id,
                "is_read": r.is_read,
                "read_at": r.read_at.isoformat() if r.read_at else None,
                "archived_at": r.archived_at.isoformat() if r.archived_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "metadata": r.metadata_json,
            }
            for r in records
        ],
        "unread_count": unread_count,
        "offset": offset,
        "limit": limit,
        "archived": archived,
    }


@router.get("/inbox/unread-count")
async def get_unread_count(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, int]:
    """Lightweight endpoint for navigation badge counter."""
    user_id = str(current_user.id)
    unread_stmt = select(func.count(NotificationRecord.id)).where(
        NotificationRecord.user_id == user_id,
        NotificationRecord.is_read.is_(False),
        NotificationRecord.archived_at.is_(None),
    )
    count = (await session.execute(unread_stmt)).scalar() or 0
    return {"unread_count": count}


@router.post("/inbox/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
) -> dict[str, Any]:
    """Marks a single notification as read, enforcing user ownership.

    Commit + re-read before responding so a hard reload ~400ms later sees read.
    """
    response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    user_id = str(current_user.id)
    res = await session.execute(
        select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.user_id == user_id,
        )
    )
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Notification not found")

    now = datetime.now(UTC)
    record.is_read = True
    record.read_at = now
    await session.flush()
    await session.commit()
    session.expire_all()
    verify = await session.execute(
        select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.user_id == user_id,
        )
    )
    verified = verify.scalar_one_or_none()
    if verified is None or not verified.is_read:
        raise HTTPException(status_code=500, detail="Mark read did not persist")
    return {
        "id": verified.id,
        "is_read": True,
        "read_at": (verified.read_at or now).isoformat(),
    }


@router.post("/inbox/read-all")
async def mark_all_read(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Marks all notifications for the authenticated user as read."""
    user_id = str(current_user.id)
    now = datetime.now(UTC)
    stmt = (
        update(NotificationRecord)
        .where(
            NotificationRecord.user_id == user_id,
            NotificationRecord.is_read.is_(False),
            NotificationRecord.archived_at.is_(None),
        )
        .values(is_read=True, read_at=now)
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"marked_read": result.rowcount, "read_at": now.isoformat()}


async def _archive_inbox_item(
    notification_id: int,
    session: AsyncSession,
    current_user: User,
) -> dict[str, Any]:
    """Persist archived_at; used by DELETE and POST archive routes.

    Explicit UPDATE + re-read so a quick reload ~0.4s later sees archived.
    """
    user_id = str(current_user.id)
    now = datetime.now(UTC)
    result = await session.execute(
        update(NotificationRecord)
        .where(
            NotificationRecord.id == notification_id,
            NotificationRecord.user_id == user_id,
        )
        .values(archived_at=now)
    )
    if int(result.rowcount or 0) < 1:
        raise HTTPException(status_code=404, detail="Notification not found")
    await session.flush()
    await session.commit()
    res = await session.execute(
        select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.user_id == user_id,
        )
    )
    record = res.scalar_one_or_none()
    if record is None or record.archived_at is None:
        raise HTTPException(status_code=500, detail="Archive did not persist")
    return {
        "id": record.id,
        "archived": True,
        "archived_at": record.archived_at.isoformat(),
    }


@router.delete("/inbox/{notification_id}")
async def archive_notification(
    notification_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Archives a notification from the inbox (DELETE)."""
    return await _archive_inbox_item(notification_id, session, current_user)


@router.post("/inbox/{notification_id}/archive")
async def archive_notification_post(
    notification_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Archives a notification (POST — preferred; survives proxies that strip DELETE)."""
    return await _archive_inbox_item(notification_id, session, current_user)


@router.post("/inbox/{notification_id}/unarchive")
async def unarchive_notification(
    notification_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Restores an archived notification back to the active inbox.

    Uses an explicit UPDATE … SET archived_at=NULL so the clear is never a
    no-op ORM dirty-check miss, then re-reads before responding.
    """
    from sqlalchemy import update

    user_id = str(current_user.id)
    result = await session.execute(
        update(NotificationRecord)
        .where(
            NotificationRecord.id == notification_id,
            NotificationRecord.user_id == user_id,
        )
        .values(archived_at=None)
    )
    if int(result.rowcount or 0) < 1:
        raise HTTPException(status_code=404, detail="Notification not found")
    await session.flush()
    await session.commit()

    res = await session.execute(
        select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.user_id == user_id,
        )
    )
    record = res.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if record.archived_at is not None:
        raise HTTPException(status_code=500, detail="Unarchive did not persist")
    return {
        "id": record.id,
        "archived": False,
        "archived_at": None,
    }


# -------------------------------------------------------------------------
# Digest Preview & Verified Test Send
# -------------------------------------------------------------------------


@router.get("/digest/preview")
async def preview_digest(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Previews the upcoming digest from actual eligible data without sending."""
    prefs = await _load_user_prefs(session, current_user)
    service = DigestService(session)
    return await service.preview_digest(current_user, prefs)


@router.post("/digest/test")
async def send_test_digest(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Sends a test digest ONLY to the authenticated verified user on explicit request."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Email verification required before sending test digests.",
        )
    prefs = await _load_user_prefs(session, current_user)
    service = DigestService(session)
    try:
        return await service.send_test_digest(current_user, prefs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/timezone-preview")
async def timezone_preview(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Returns local time, timezone offset, DST status, and next scheduled send."""
    prefs = await _load_user_prefs(session, current_user)
    return calculate_next_send(prefs)


# -------------------------------------------------------------------------
# Provider Observability & Webhook Ingestion
# -------------------------------------------------------------------------


@router.get("/providers/status")
async def provider_status(
    session: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Provides observable delivery provider health and metrics without exposing PII."""
    outbox_svc = OutboxService(session)
    return await outbox_svc.get_provider_status()


@router.get("/providers/capabilities")
async def provider_capabilities(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Exposes provider configuration states to feature-flag unverified providers in UI."""
    return {
        "email": {
            "resend_enabled": bool(os.getenv("RESEND_API_KEY")),
            "smtp_enabled": bool(os.getenv("EMAIL_SMTP_HOST")),
            "verified": bool(os.getenv("RESEND_API_KEY") or os.getenv("EMAIL_SMTP_HOST")),
        },
        "slack": {
            "enabled": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "verified": bool(os.getenv("SLACK_WEBHOOK_URL")),
        },
        "discord": {
            "enabled": bool(os.getenv("DISCORD_WEBHOOK_URL")),
            "verified": bool(os.getenv("DISCORD_WEBHOOK_URL")),
        },
        "telegram": {
            "enabled": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "verified": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        },
        "whatsapp": {
            "enabled": bool(os.getenv("WHATSAPP_TWILIO_SID")),
            "verified": bool(os.getenv("WHATSAPP_TWILIO_SID")),
        },
        "in_app": {
            "enabled": True,
            "verified": True,
        },
    }


@router.post("/webhook/{provider}")
async def handle_provider_webhook(
    provider: str,
    payload: WebhookPayload,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_webhook_secret: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Handles webhook callbacks from delivery providers for bounces, complaints, and unsubscribes.

    Authenticates webhook requests and automatically safeguards sender reputation.
    """
    configured_secret = os.getenv("WEBHOOK_SECRET") or os.getenv("RESEND_WEBHOOK_SECRET")
    if configured_secret:
        if not x_webhook_secret or not hmac.compare_digest(
            x_webhook_secret, configured_secret
        ):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_kind = payload.event.lower()
    target_email = payload.email or payload.recipient

    # Safeguard sender reputation on hard bounces, complaints, or unsubscribes
    if event_kind in {
        "email.bounced",
        "bounce",
        "hard_bounce",
        "email.complained",
        "complaint",
        "spam_report",
        "unsubscribe",
        "email.unsubscribed",
    }:
        if target_email:
            now = datetime.now(UTC)
            # Locate user and update subscription status
            user_res = await session.execute(
                select(User).where(User.email == target_email)
            )
            user = user_res.scalar_one_or_none()
            if user:
                pref_res = await session.execute(
                    select(UserPreferences).where(UserPreferences.user_id == user.id)
                )
                prefs = pref_res.scalar_one_or_none()
                if prefs:
                    prefs.is_unsubscribed = True
                    prefs.unsubscribed_at = now
                    prefs.notes = (
                        f"Unsubscribed via {provider} webhook event '{event_kind}': {payload.reason or 'reputation protection'}"
                    )
                    session.add(prefs)
                    await session.commit()
                    return {
                        "status": "unsubscribed",
                        "user_id": user.id,
                        "event": event_kind,
                    }

    # If delivery success
    if event_kind in {"email.delivered", "delivered"} and payload.message_id:
        outbox_res = await session.execute(
            select(NotificationOutbox).where(
                NotificationOutbox.dedup_key.like(f"%{payload.message_id}%")
            )
        )
        record = outbox_res.scalar_one_or_none()
        if record:
            record.status = "delivered"
            record.delivered_at = datetime.now(UTC)
            await session.commit()

    return {"status": "processed", "provider": provider, "event": event_kind}


@router.get("/retry-queue")
async def retry_queue(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    return {"items": [entry.__dict__ for entry in legacy_service.get_retry_queue()]}
