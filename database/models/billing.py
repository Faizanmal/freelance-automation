"""Billing, Quota Reservations, and Subscription Lifecycle Database Models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from database.core.base import Base


class BillingWebhookEvent(Base):
    """Tracks received webhook events for deduplication, replay defense, and out-of-order handling."""

    __tablename__ = "billing_webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="stripe")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="processed"
    )  # processed, duplicate, ignored, failed
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class QuotaReservationRecord(Base):
    """Atomic quota reservation to prevent race-driven overspend of expensive AI/search operations."""

    __tablename__ = "quota_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: f"res_{uuid4().hex}"
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # copilot_run, token_budget, search_call
    units_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    units_committed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="reserved", index=True
    )  # reserved, committed, released, expired
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class UsageRecord(Base):
    """Aggregated usage records per user, feature, and billing period."""

    __tablename__ = "user_usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    period_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # e.g. YYYY-MM or YYYY-MM-DD
    units_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_estimate_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class SubscriptionLifecycleRecord(Base):
    """Detailed subscription state tracking including grace periods and event order."""

    __tablename__ = "subscription_lifecycle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="stripe")
    customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="inactive"
    )  # active, trialing, past_due, canceled, in_grace, dev
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_period_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
