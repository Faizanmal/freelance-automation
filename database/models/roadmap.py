from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from database.core.base import Base


class RoadmapVote(Base):
    __tablename__ = "roadmap_votes"
    __table_args__ = (
        UniqueConstraint("feature_key", "voter_id", name="uq_roadmap_vote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    voter_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class CancellationFeedback(Base):
    __tablename__ = "cancellation_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
