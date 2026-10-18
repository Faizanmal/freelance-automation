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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.core.base import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    exclude_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    min_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    match_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.35)
    notification_channels: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    digest_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    freelance_focus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    digest_days: Mapped[list | None] = mapped_column(JSON, nullable=True)
    digest_time_local: Mapped[str | None] = mapped_column(String(8), nullable=True)
    max_per_digest: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    digest_last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    slack_webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    discord_webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    whatsapp_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="preferences")
