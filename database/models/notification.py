from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.core.base import Base


class NotificationRecord(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    digest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="lead_match"
    )
    group_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class NotificationOutbox(Base):
    """Transactional outbox / delivery log for idempotent, retryable multi-channel sends."""

    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dedup_key: Mapped[str] = mapped_column(
        String(256), unique=True, nullable=False, index=True
    )
    recipient: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="lead_match", index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class DigestSentJob(Base):
    """Tracks which job leads have already been delivered to each user to prevent repeat entries."""

    __tablename__ = "digest_sent_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    digest_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), index=True
    )
