"""Consent-gated, minimal product outcome events for learning."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database.core.base import Base


class ProductEvent(Base):
    __tablename__ = "product_events"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_product_event_user_key"),
        Index("ix_product_events_name_environment_time", "event_name", "environment", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(36), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Only tightly allow-listed categorical metadata is accepted by the API.
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
