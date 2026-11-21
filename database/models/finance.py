"""Phase 10 — Freelancer Financial Intelligence & Earnings Workspace Models.

Informational planning and transparent fee breakdown — not tax/financial advice.
Does not hold or move money, nor store bank account credentials.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.core.base import Base


class FeeTemplateRecord(Base):
    """Versioned fee templates with verified official sources, region, and effective dates."""

    __tablename__ = "fee_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    contract_service_fee_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    contract_service_fee_fixed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_on_fee_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    withholding_tax_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    withholding_base: Mapped[str] = mapped_column(String(16), nullable=False, default="gross")  # gross | fee
    withdrawal_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    withdrawal_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    processor_charge_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    processor_charge_fixed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    effective_date: Mapped[str] = mapped_column(String(32), nullable=False)
    eligibility_notes: Mapped[str] = mapped_column(Text, nullable=False)
    is_system_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class FxRateCacheRecord(Base):
    """Cached FX conversion rates with explicit benchmark (mid-market) vs offered bank rates."""

    __tablename__ = "fx_rate_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    quote_currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    benchmark_rate: Mapped[float] = mapped_column(Float, nullable=False)
    offered_rate: Mapped[float] = mapped_column(Float, nullable=False)
    rate_type: Mapped[str] = mapped_column(String(32), nullable=False, default="estimated_platform")  # mid_market, bank_transfer, platform_fx
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False, default="open_er_or_manual")
    is_outage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class UserEarningRecord(Base):
    """User-confirmed won projects and earnings records (strictly separates cash received from pipeline)."""

    __tablename__ = "user_earnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_title: Mapped[str] = mapped_column(String(256), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, default="direct")
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    invoice_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="invoiced", index=True
    )  # draft, invoiced, paid, cancelled
    gross_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    platform_fee_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_on_fee_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    withholding_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    withdrawal_fee_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    processor_fee_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_received_usd: Mapped[float] = mapped_column(Float, nullable=False)
    net_received_local: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    actual_fx_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    hours_logged: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
