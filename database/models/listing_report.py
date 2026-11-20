"""User listing reports → moderator queue (trust / abuse / correction)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.core.base import Base


class ListingReport(Base):
    __tablename__ = "listing_reports"
    __table_args__ = (
        UniqueConstraint(
            "reporter_user_id",
            "job_id",
            "reason_code",
            name="uq_listing_report_user_job_reason",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter_user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    # open → in_review → resolved | dismissed | corrected
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", index=True
    )
    severity_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Avoid storing unnecessary PII — strip emails/phones in service layer
    sanitized_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_report_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    moderator_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    moderator_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    moderator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_requested: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ListingReportCorrection(Base):
    __tablename__ = "listing_report_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("listing_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
