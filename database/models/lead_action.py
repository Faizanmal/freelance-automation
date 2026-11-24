from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.core.base import Base


class UserLeadAction(Base):
    """Per-user Save / Skip + Phase 08 pipeline CRM fields for a lead (job)."""

    __tablename__ = "user_lead_actions"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_lead_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # save | skip | pitched | won
    # Optional structured feedback (Phase 07) — not every click is success.
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feedback_kind: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # save | skip | hide_source | apply_click | outcome | clear
    # Phase 08 CRM — explicit stage; status kept for Save/Skip / ranking semantics.
    pipeline_stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default="saved", index=True
    )
    follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    apply_clicked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tags: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    employer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    contact_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    won_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # Monotonic client write version so a late original write cannot override Undo.
    client_write_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    # passive_deletes: rely on FK ON DELETE CASCADE instead of ORM nulling user_id
    user = relationship(
        "User",
        back_populates="lead_actions",
        passive_deletes=True,
    )
