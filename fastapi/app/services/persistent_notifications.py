from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationDelivery, NotificationRecord
from app.services.notification_service import (
    NotificationPayload,
    NotificationResult,
    NotificationService,
)


class PersistentNotificationService:
    """Wraps the in-memory dispatcher and writes durable history."""

    def __init__(self, session: AsyncSession, dispatcher: NotificationService | None = None) -> None:
        self.session = session
        self.dispatcher = dispatcher or NotificationService()

    async def send(self, payload: NotificationPayload, *, job_id: int | None = None) -> dict[str, object]:
        public_id = str(uuid4())
        record = NotificationRecord(
            public_id=public_id,
            user_id=payload.user_id,
            title=payload.title,
            body=payload.body,
            channels=[channel.value for channel in payload.channels],
            priority=payload.priority.value,
            digest=payload.digest,
            ai_summary=payload.ai_summary,
            status="sending",
            job_id=job_id,
            metadata_json=payload.metadata or {},
        )
        self.session.add(record)
        await self.session.flush()

        results = await self.dispatcher.dispatch(payload)
        delivered_any = False
        for result in results:
            delivered_any = delivered_any or result.delivered
            self.session.add(
                NotificationDelivery(
                    notification_id=record.id,
                    channel=result.channel.value,
                    delivered=result.delivered,
                    message_id=result.message_id,
                    error=result.error,
                )
            )

        record.status = "delivered" if delivered_any else "failed"
        await self.session.commit()
        await self.session.refresh(record)

        return {
            "id": record.id,
            "public_id": record.public_id,
            "status": record.status,
            "results": [_result_dict(result) for result in results],
        }


def _result_dict(result: NotificationResult) -> dict[str, object]:
    return {
        "channel": result.channel.value,
        "delivered": result.delivered,
        "message_id": result.message_id,
        "error": result.error,
    }
