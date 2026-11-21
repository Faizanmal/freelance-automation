"""Transactional Outbox and Delivery Log service.

Guarantees idempotency via unique dedup_key (event + recipient + channel + reference/date),
bounded retries with dead-letter queue, cost accounting, and observable provider metrics
without leaking recipient PII.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import os
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.services.notification_service import (
    DeliveryAdapter,
    EmailAdapter,
    NotificationChannel,
    NotificationEnvelope,
    NotificationPriority,
    NotificationResult,
    NotificationService,
)
from database.models.notification import NotificationDelivery, NotificationOutbox, NotificationRecord

# Estimated unit cost per provider delivery in USD
PROVIDER_UNIT_COSTS: dict[str, float] = {
    "email": 0.0008,      # Resend / transactional email
    "slack": 0.0000,      # Free webhook
    "discord": 0.0000,    # Free webhook
    "telegram": 0.0000,   # Free bot message
    "webhook": 0.0000,    # Free webhook
    "whatsapp": 0.0100,   # Twilio WhatsApp message
    "in_app": 0.0000,     # Internal database entry
}


class OutboxService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: NotificationService | None = None,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher or NotificationService()

    async def enqueue(
        self,
        *,
        dedup_key: str,
        recipient: str,
        channel: str,
        title: str,
        body: str,
        html_body: str | None = None,
        event_type: str = "lead_match",
        payload_json: dict[str, Any] | None = None,
        user_id: str | None = None,
        scheduled_for: datetime | None = None,
        cost_usd: float | None = None,
        max_retries: int = 3,
    ) -> tuple[NotificationOutbox, bool]:
        """Enqueues an outbox record idempotently.

        Returns:
            (outbox_record, is_newly_created)
        """
        # 1. Idempotency check on unique dedup_key
        existing_res = await self.session.execute(
            select(NotificationOutbox).where(NotificationOutbox.dedup_key == dedup_key)
        )
        existing = existing_res.scalar_one_or_none()
        if existing:
            return existing, False

        unit_cost = (
            cost_usd
            if cost_usd is not None
            else PROVIDER_UNIT_COSTS.get(channel.lower(), 0.0)
        )

        record = NotificationOutbox(
            dedup_key=dedup_key,
            recipient=recipient,
            user_id=user_id,
            channel=channel.lower(),
            event_type=event_type,
            title=title,
            body=body,
            html_body=html_body,
            payload_json=payload_json or {},
            status="pending",
            attempts=0,
            max_retries=max_retries,
            cost_usd=unit_cost,
            scheduled_for=scheduled_for or datetime.now(UTC),
        )
        self.session.add(record)
        await self.session.flush()
        return record, True

    async def deliver_record(
        self, record: NotificationOutbox
    ) -> NotificationResult:
        """Attempts delivery of a single outbox record with bounded retries."""
        record.attempts += 1
        record.last_attempt_at = datetime.now(UTC)
        record.status = "sending"

        # Resolve channel enum
        try:
            channel_enum = NotificationChannel(record.channel)
        except ValueError:
            record.status = "dead_letter"
            record.last_error = f"Unsupported channel: {record.channel}"
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                delivered=False,
                error=record.last_error,
            )

        envelope = NotificationEnvelope(
            id=f"outbox-{record.id}",
            user_id=record.user_id or "system",
            title=record.title,
            body=record.body,
            channels=[channel_enum],
            priority=NotificationPriority.NORMAL,
            digest=record.event_type == "digest",
            ai_summary=None,
            actions=[],
            metadata=record.payload_json or {},
            destinations={record.channel: record.recipient},
        )

        adapter: DeliveryAdapter = self.dispatcher._channel_adapters.get(
            channel_enum, EmailAdapter()
        )

        try:
            result = await adapter.send(envelope)
        except Exception as exc:
            result = NotificationResult(
                channel=channel_enum,
                delivered=False,
                error=str(exc)[:250],
            )

        if result.delivered:
            record.status = "delivered"
            record.delivered_at = datetime.now(UTC)
            record.last_error = None
        else:
            record.last_error = result.error or "delivery_failed"
            if record.attempts >= record.max_retries:
                record.status = "dead_letter"
            else:
                record.status = "failed"

        await self.session.flush()
        return result

    async def process_pending_outbox(
        self, batch_size: int = 50
    ) -> dict[str, int]:
        """Pulls pending or retryable outbox items and attempts delivery."""
        now = datetime.now(UTC)
        stmt = (
            select(NotificationOutbox)
            .where(
                NotificationOutbox.scheduled_for <= now,
                (NotificationOutbox.status == "pending")
                | (
                    (NotificationOutbox.status == "failed")
                    & (NotificationOutbox.attempts < NotificationOutbox.max_retries)
                ),
            )
            .order_by(NotificationOutbox.scheduled_for.asc())
            .limit(batch_size)
        )
        res = await self.session.execute(stmt)
        records = list(res.scalars().all())

        delivered = 0
        failed = 0
        dead_letter = 0

        for record in records:
            result = await self.deliver_record(record)
            if result.delivered:
                delivered += 1
            elif record.status == "dead_letter":
                dead_letter += 1
            else:
                failed += 1

        if records:
            await self.session.commit()

        return {
            "processed": len(records),
            "delivered": delivered,
            "failed": failed,
            "dead_letter": dead_letter,
        }

    async def get_provider_status(self) -> dict[str, Any]:
        """Provides operational metrics on all delivery providers without leaking recipient PII."""
        # Provider configuration presence
        resend_key = os.getenv("RESEND_API_KEY")
        smtp_host = os.getenv("EMAIL_SMTP_HOST")
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        discord_url = os.getenv("DISCORD_WEBHOOK_URL")
        slack_url = os.getenv("SLACK_WEBHOOK_URL")
        whatsapp_sid = os.getenv("WHATSAPP_TWILIO_SID")

        # Delivery statistics from outbox
        status_stmt = select(
            NotificationOutbox.status,
            func.count(NotificationOutbox.id),
            func.sum(NotificationOutbox.cost_usd),
        ).group_by(NotificationOutbox.status)
        status_res = await self.session.execute(status_stmt)
        status_counts: dict[str, int] = {}
        total_cost = 0.0
        for status, count, cost in status_res.all():
            status_counts[str(status)] = int(count)
            total_cost += float(cost or 0.0)

        # Channel breakdowns
        chan_stmt = select(
            NotificationOutbox.channel,
            NotificationOutbox.status,
            func.count(NotificationOutbox.id),
        ).group_by(NotificationOutbox.channel, NotificationOutbox.status)
        chan_res = await self.session.execute(chan_stmt)
        channel_metrics: dict[str, dict[str, int]] = {}
        for chan, st, count in chan_res.all():
            c_dict = channel_metrics.setdefault(str(chan), {})
            c_dict[str(st)] = int(count)

        return {
            "providers": {
                "email_resend": {
                    "configured": bool(resend_key),
                    "status": "operational" if resend_key else "unconfigured",
                },
                "email_smtp": {
                    "configured": bool(smtp_host),
                    "status": "operational" if smtp_host else "unconfigured",
                },
                "telegram": {
                    "configured": bool(telegram_token),
                    "status": "operational" if telegram_token else "unconfigured",
                },
                "slack": {
                    "configured": bool(slack_url),
                    "status": "operational" if slack_url else "unconfigured",
                },
                "discord": {
                    "configured": bool(discord_url),
                    "status": "operational" if discord_url else "unconfigured",
                },
                "whatsapp": {
                    "configured": bool(whatsapp_sid),
                    "status": "operational" if whatsapp_sid else "unconfigured",
                },
                "in_app": {
                    "configured": True,
                    "status": "operational",
                },
            },
            "delivery_totals": {
                "delivered": status_counts.get("delivered", 0),
                "pending": status_counts.get("pending", 0),
                "failed": status_counts.get("failed", 0),
                "dead_letter": status_counts.get("dead_letter", 0),
                "total_estimated_cost_usd": round(total_cost, 4),
            },
            "channels": channel_metrics,
        }
