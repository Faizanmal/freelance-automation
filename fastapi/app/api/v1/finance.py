"""Freelancer financial intelligence & earnings calculator API endpoints.

This module is strictly informational and does not constitute formal financial,
legal, or tax advice. It does not move funds or store sensitive bank account credentials.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from backend.application.services.fee_templates import FeeTemplateService
from backend.application.services.financial_calculator import (
    CalculationBreakdown,
    FinancialCalculator,
    InverseQuoteResult,
)
from backend.application.services.fx_service import FxService
from database.core.session import get_db
from database.models.finance import UserEarningRecord
from database.models.user import User

router = APIRouter(prefix="/finance", tags=["financial-intelligence"])

LEGAL_DISCLAIMER = (
    "Informational estimate only. Not formal financial, legal, or tax advice. "
    "Platform does not move funds or guarantee live foreign exchange execution rates."
)


# ---------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------

class GrossToNetRequest(BaseModel):
    gross_amount: float = Field(..., ge=0, description="Gross billed contract amount")
    currency: str = Field(default="USD", max_length=6)
    target_currency: str | None = Field(default=None, max_length=6)
    template_id: str | None = None
    contract_service_fee_pct: float = Field(default=0.0, ge=0)
    contract_service_fee_fixed: float = Field(default=0.0, ge=0)
    fee_tax_pct: float = Field(default=0.0, ge=0)
    withholding_tax_pct: float = Field(default=0.0, ge=0)
    withholding_tax_base: Literal["gross", "fee"] = "gross"
    withdrawal_fee: float = Field(default=0.0, ge=0)
    withdrawal_count: int = Field(default=1, ge=1)
    processor_fee_pct: float = Field(default=0.0, ge=0)
    processor_fee_fixed: float = Field(default=0.0, ge=0)
    other_expenses: float = Field(default=0.0, ge=0)
    benchmark_fx_rate: float | None = Field(default=None, gt=0)
    actual_fx_rate: float | None = Field(default=None, gt=0)
    reported_bank_quote: float | None = Field(default=None, gt=0)


class NetToGrossRequest(BaseModel):
    target_net_amount: float = Field(..., gt=0, description="Desired net deposit amount")
    currency: str = Field(default="USD", max_length=6)
    target_currency: str | None = Field(default=None, max_length=6)
    hourly_hours: float | None = Field(default=None, gt=0, description="If quoting hourly rate")
    contract_service_fee_pct: float = Field(default=0.0, ge=0)
    contract_service_fee_fixed: float = Field(default=0.0, ge=0)
    fee_tax_pct: float = Field(default=0.0, ge=0)
    withholding_tax_pct: float = Field(default=0.0, ge=0)
    withholding_tax_base: Literal["gross", "fee"] = "gross"
    withdrawal_fee: float = Field(default=0.0, ge=0)
    withdrawal_count: int = Field(default=1, ge=1)
    processor_fee_pct: float = Field(default=0.0, ge=0)
    processor_fee_fixed: float = Field(default=0.0, ge=0)
    other_expenses: float = Field(default=0.0, ge=0)
    actual_fx_rate: float | None = Field(default=None, gt=0)


class ScenarioInput(BaseModel):
    name: str
    template_id: str | None = None
    contract_service_fee_pct: float = 0.0
    contract_service_fee_fixed: float = 0.0
    fee_tax_pct: float = 0.0
    withholding_tax_pct: float = 0.0
    withholding_tax_base: Literal["gross", "fee"] = "gross"
    withdrawal_fee: float = 0.0
    withdrawal_count: int = 1
    processor_fee_pct: float = 0.0
    processor_fee_fixed: float = 0.0
    other_expenses: float = 0.0
    benchmark_fx_rate: float | None = None
    actual_fx_rate: float | None = None


class CompareScenariosRequest(BaseModel):
    gross_amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=6)
    target_currency: str | None = None
    scenarios: list[ScenarioInput]


class WithdrawalFrequencyRequest(BaseModel):
    annual_gross: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=6)
    withdrawal_fee: float = Field(..., ge=0)
    custom_counts: dict[str, int] | None = None


class FeeTemplateCreate(BaseModel):
    template_name: str = Field(..., max_length=120)
    platform: str = Field(default="custom", max_length=60)
    region: str = Field(default="GLOBAL", max_length=40)
    currency: str = Field(default="USD", max_length=6)
    contract_service_fee_pct: float = Field(default=0.0, ge=0)
    contract_service_fee_fixed: float = Field(default=0.0, ge=0)
    fee_tax_pct: float = Field(default=0.0, ge=0)
    withholding_tax_pct: float = Field(default=0.0, ge=0)
    withholding_tax_base: Literal["gross", "fee"] = "gross"
    withdrawal_fee: float = Field(default=0.0, ge=0)
    processor_fee_pct: float = Field(default=0.0, ge=0)
    processor_fee_fixed: float = Field(default=0.0, ge=0)
    source_url: str = Field(default="", max_length=500)
    effective_date: str = Field(default="", max_length=30)
    eligibility_notes: str = Field(default="", max_length=500)


class UserEarningCreate(BaseModel):
    project_title: str = Field(..., max_length=200)
    client_name: str | None = Field(default=None, max_length=150)
    platform: str = Field(default="upwork", max_length=60)
    job_id: int | None = None
    currency: str = Field(default="USD", max_length=6)
    gross_amount: float = Field(..., ge=0)
    contract_service_fee: float = Field(default=0.0, ge=0)
    fee_tax: float = Field(default=0.0, ge=0)
    withholding_tax: float = Field(default=0.0, ge=0)
    withdrawal_fee: float = Field(default=0.0, ge=0)
    processor_fee: float = Field(default=0.0, ge=0)
    other_expenses: float = Field(default=0.0, ge=0)
    actual_fx_rate: float | None = Field(default=None, gt=0)
    target_currency: str | None = None
    net_payout_amount: float | None = None
    net_received_in_bank: float | None = None
    invoice_status: Literal["draft", "invoiced", "paid", "cancelled"] = "draft"
    payment_date: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class UserEarningUpdate(BaseModel):
    project_title: str | None = None
    client_name: str | None = None
    platform: str | None = None
    currency: str | None = None
    gross_amount: float | None = None
    contract_service_fee: float | None = None
    fee_tax: float | None = None
    withholding_tax: float | None = None
    withdrawal_fee: float | None = None
    processor_fee: float | None = None
    actual_fx_rate: float | None = None
    net_payout_amount: float | None = None
    net_received_in_bank: float | None = None
    invoice_status: Literal["draft", "invoiced", "paid", "cancelled"] | None = None
    payment_date: datetime | None = None
    notes: str | None = None


# ---------------------------------------------------------
# Calculator Endpoints
# ---------------------------------------------------------

@router.post("/calculate")
async def calculate_gross_to_net(
    payload: GrossToNetRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Calculate net take-home from gross contract amount with explicit fee breakdown."""
    fee_pct = payload.contract_service_fee_pct
    fee_fixed = payload.contract_service_fee_fixed
    fee_tax = payload.fee_tax_pct
    withholding_pct = payload.withholding_tax_pct
    withholding_base = payload.withholding_tax_base
    withdrawal_fee = payload.withdrawal_fee
    processor_pct = payload.processor_fee_pct
    processor_fixed = payload.processor_fee_fixed

    if payload.template_id:
        tpl_service = FeeTemplateService(session)
        tpl = await tpl_service.get_template_by_id(payload.template_id)
        if tpl:
            fee_pct = tpl["contract_service_fee_pct"]
            fee_fixed = tpl["contract_service_fee_fixed"]
            fee_tax = tpl["fee_tax_pct"]
            withholding_pct = tpl["withholding_tax_pct"]
            withholding_base = tpl["withholding_tax_base"]
            withdrawal_fee = tpl["withdrawal_fee"]
            processor_pct = tpl["processor_fee_pct"]
            processor_fixed = tpl["processor_fee_fixed"]

    actual_fx = payload.actual_fx_rate
    benchmark_fx = payload.benchmark_fx_rate
    fx_meta = None
    if payload.target_currency and payload.target_currency.upper() != payload.currency.upper():
        fx_svc = FxService(session)
        fx_meta = await fx_svc.get_fx_rate(
            from_currency=payload.currency,
            to_currency=payload.target_currency,
            manual_rate=payload.actual_fx_rate,
        )
        if actual_fx is None:
            actual_fx = fx_meta["offered_rate"]
        if benchmark_fx is None:
            benchmark_fx = fx_meta["benchmark_rate"]

    breakdown = FinancialCalculator.calculate_gross_to_net(
        gross_amount=payload.gross_amount,
        currency=payload.currency,
        contract_service_fee_pct=fee_pct,
        contract_service_fee_fixed=fee_fixed,
        fee_tax_pct=fee_tax,
        withholding_tax_pct=withholding_pct,
        withholding_tax_base=withholding_base,
        withdrawal_fee=withdrawal_fee,
        withdrawal_count=payload.withdrawal_count,
        processor_fee_pct=processor_pct,
        processor_fee_fixed=processor_fixed,
        other_expenses=payload.other_expenses,
        benchmark_fx_rate=benchmark_fx,
        actual_fx_rate=actual_fx,
        target_currency=payload.target_currency,
        reported_bank_quote=payload.reported_bank_quote,
    )

    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "calculation": breakdown.to_dict(),
        "fx_metadata": fx_meta,
    }


@router.post("/calculate/inverse")
async def calculate_net_to_gross(
    payload: NetToGrossRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Calculate the required gross quote to guarantee desired net bank deposit."""
    result = FinancialCalculator.calculate_net_to_gross(
        target_net_amount=payload.target_net_amount,
        currency=payload.currency,
        contract_service_fee_pct=payload.contract_service_fee_pct,
        contract_service_fee_fixed=payload.contract_service_fee_fixed,
        fee_tax_pct=payload.fee_tax_pct,
        withholding_tax_pct=payload.withholding_tax_pct,
        withholding_tax_base=payload.withholding_tax_base,
        withdrawal_fee=payload.withdrawal_fee,
        withdrawal_count=payload.withdrawal_count,
        processor_fee_pct=payload.processor_fee_pct,
        processor_fee_fixed=payload.processor_fee_fixed,
        other_expenses=payload.other_expenses,
        actual_fx_rate=payload.actual_fx_rate,
        target_currency=payload.target_currency,
        hourly_hours=payload.hourly_hours,
    )

    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "quote": result.to_dict(),
    }


@router.post("/calculate/compare")
async def compare_scenarios(
    payload: CompareScenariosRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Compare multiple fee structures and platforms side by side."""
    tpl_service = FeeTemplateService(session)
    resolved_scenarios = []

    for sc in payload.scenarios:
        s_dict = sc.model_dump()
        if sc.template_id:
            tpl = await tpl_service.get_template_by_id(sc.template_id)
            if tpl:
                s_dict.update({
                    "contract_service_fee_pct": tpl["contract_service_fee_pct"],
                    "contract_service_fee_fixed": tpl["contract_service_fee_fixed"],
                    "fee_tax_pct": tpl["fee_tax_pct"],
                    "withholding_tax_pct": tpl["withholding_tax_pct"],
                    "withholding_tax_base": tpl["withholding_tax_base"],
                    "withdrawal_fee": tpl["withdrawal_fee"],
                    "processor_fee_pct": tpl["processor_fee_pct"],
                    "processor_fee_fixed": tpl["processor_fee_fixed"],
                })
        resolved_scenarios.append(s_dict)

    comparisons = FinancialCalculator.compare_scenarios(
        gross_amount=payload.gross_amount,
        currency=payload.currency,
        scenarios=resolved_scenarios,
        target_currency=payload.target_currency,
    )

    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "gross_amount": payload.gross_amount,
        "currency": payload.currency,
        "scenarios": comparisons,
    }


@router.post("/calculate/withdrawal-frequencies")
async def simulate_withdrawal_frequencies(
    payload: WithdrawalFrequencyRequest,
) -> dict[str, Any]:
    """Calculate annual drag of withdrawal frequency choices (daily vs weekly vs monthly)."""
    results = FinancialCalculator.simulate_withdrawal_frequencies(
        annual_gross=payload.annual_gross,
        currency=payload.currency,
        withdrawal_fee=payload.withdrawal_fee,
        withdrawal_counts=payload.custom_counts,
    )
    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "annual_gross": payload.annual_gross,
        "currency": payload.currency,
        "withdrawal_fee": payload.withdrawal_fee,
        "frequencies": results,
    }


# ---------------------------------------------------------
# Fee Templates Endpoints
# ---------------------------------------------------------

@router.get("/templates")
async def list_fee_templates(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """List system official and verified platform fee templates."""
    svc = FeeTemplateService(session)
    templates = await svc.list_templates()
    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "templates": templates,
    }


@router.post("/templates")
async def create_user_fee_template(
    payload: FeeTemplateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Create a customized fee template for an authenticated user."""
    svc = FeeTemplateService(session)
    record = await svc.create_custom_template(current_user.id, payload.model_dump())
    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "template": {
            "id": f"tpl_{record.id}",
            "slug": record.slug,
            "template_name": record.name,
            "name": record.name,
            "platform": record.platform,
            "region": record.region,
            "currency": record.withdrawal_currency,
            "contract_service_fee_pct": record.contract_service_fee_pct,
            "contract_service_fee_fixed": record.contract_service_fee_fixed,
            "fee_tax_pct": record.tax_on_fee_pct,
            "withholding_tax_pct": record.withholding_tax_pct,
            "withholding_tax_base": record.withholding_base,
            "withdrawal_fee": record.withdrawal_fee,
            "processor_fee_pct": record.processor_charge_pct,
            "processor_fee_fixed": record.processor_charge_fixed,
            "source_url": record.source_url,
            "effective_date": record.effective_date,
            "eligibility_notes": record.eligibility_notes,
            "is_system": False,
        },
    }


@router.delete("/templates/{template_id}")
async def delete_user_fee_template(
    template_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Delete a user-created custom template."""
    svc = FeeTemplateService(session)
    deleted = await svc.delete_custom_template(template_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found or cannot be deleted")
    return {"status": "deleted", "template_id": template_id}


# ---------------------------------------------------------
# FX Rates Endpoint
# ---------------------------------------------------------

@router.get("/fx-rates")
async def get_fx_rates(
    session: Annotated[AsyncSession, Depends(get_db)],
    from_currency: str = Query(default="USD", max_length=6),
    to_currency: str = Query(default="INR", max_length=6),
    manual_rate: float | None = Query(default=None, gt=0),
) -> dict[str, Any]:
    """Get transparent FX rate resolution with benchmark vs offered rates."""
    fx_svc = FxService(session)
    rate_info = await fx_svc.get_fx_rate(
        from_currency=from_currency,
        to_currency=to_currency,
        manual_rate=manual_rate,
    )
    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "rate": rate_info,
    }


# ---------------------------------------------------------
# User Earnings Workspace Endpoints
# ---------------------------------------------------------

@router.get("/earnings")
async def list_user_earnings(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(default=None),
) -> dict[str, Any]:
    """List user-confirmed won projects and earnings summary.
    
    Strictly separates confirmed cash received from estimated pipeline / draft earnings.
    """
    stmt = select(UserEarningRecord).where(
        UserEarningRecord.user_id == current_user.id
    ).order_by(UserEarningRecord.created_at.desc())

    if status_filter:
        stmt = stmt.where(UserEarningRecord.invoice_status == status_filter)

    res = await session.execute(stmt)
    records = res.scalars().all()

    cash_received = Decimal("0.00")
    gross_invoiced_paid = Decimal("0.00")
    pipeline_estimated_gross = Decimal("0.00")
    total_platform_fees_paid = Decimal("0.00")
    total_withholding_credits_paid = Decimal("0.00")
    monthly_map: dict[str, dict[str, Decimal]] = {}

    earnings_list = []
    for r in records:
        gross_d = Decimal(str(r.gross_amount))
        received_d = Decimal(str(r.net_received_usd))
        fee_d = Decimal(str(r.platform_fee_paid))
        tax_credit_d = Decimal(str(r.withholding_paid))

        if r.invoice_status == "paid":
            cash_received += received_d
            gross_invoiced_paid += gross_d
            total_platform_fees_paid += fee_d
            total_withholding_credits_paid += tax_credit_d

            date_key = (r.paid_at or r.created_at).strftime("%Y-%m")
            if date_key not in monthly_map:
                monthly_map[date_key] = {
                    "gross": Decimal("0.00"),
                    "net_cash": Decimal("0.00"),
                    "fees": Decimal("0.00"),
                    "credits": Decimal("0.00"),
                }
            monthly_map[date_key]["gross"] += gross_d
            monthly_map[date_key]["net_cash"] += received_d
            monthly_map[date_key]["fees"] += fee_d
            monthly_map[date_key]["credits"] += tax_credit_d
        elif r.invoice_status in ("draft", "invoiced"):
            # Never mix pipeline into cash received
            pipeline_estimated_gross += gross_d

        earnings_list.append({
            "id": str(r.id),
            "project_title": r.project_title,
            "client_name": r.client_name,
            "platform": r.platform,
            "job_id": r.job_id,
            "currency": r.currency,
            "gross_amount": r.gross_amount,
            "contract_service_fee": r.platform_fee_paid,
            "fee_tax": r.tax_on_fee_paid,
            "withholding_tax": r.withholding_paid,
            "withdrawal_fee": r.withdrawal_fee_paid,
            "processor_fee": r.processor_fee_paid,
            "actual_fx_rate": r.actual_fx_rate,
            "net_payout_amount": r.net_received_usd,
            "net_received_in_bank": r.net_received_local or r.net_received_usd,
            "invoice_status": r.invoice_status,
            "payment_date": r.paid_at.isoformat() if r.paid_at else None,
            "notes": r.notes,
            "created_at": r.created_at.isoformat(),
        })

    effective_take_home_rate = 0.0
    if gross_invoiced_paid > 0:
        effective_take_home_rate = float(
            round((cash_received / gross_invoiced_paid) * Decimal("100.0"), 2)
        )

    monthly_summary = [
        {
            "month": m,
            "gross": float(data["gross"]),
            "net_cash": float(data["net_cash"]),
            "fees": float(data["fees"]),
            "withholding_credits": float(data["credits"]),
        }
        for m, data in sorted(monthly_map.items())
    ]

    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "summary": {
            "cash_received": float(cash_received),
            "gross_paid": float(gross_invoiced_paid),
            "pipeline_estimated_gross": float(pipeline_estimated_gross),
            "platform_fees_paid": float(total_platform_fees_paid),
            "withholding_tax_credits": float(total_withholding_credits_paid),
            "effective_take_home_rate_pct": effective_take_home_rate,
            "monthly_summary": monthly_summary,
        },
        "earnings": earnings_list,
    }


@router.post("/earnings", status_code=status.HTTP_201_CREATED)
async def create_user_earning(
    payload: UserEarningCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Record a user-confirmed won project or invoice.
    
    Zero sensitive bank credentials or account numbers are collected or stored.
    """
    now = datetime.now(timezone.utc)

    net_usd = payload.net_payout_amount
    net_local = payload.net_received_in_bank

    if net_usd is None:
        calc = FinancialCalculator.calculate_gross_to_net(
            gross_amount=payload.gross_amount,
            currency=payload.currency,
            contract_service_fee_fixed=payload.contract_service_fee,
            withdrawal_fee=payload.withdrawal_fee,
            processor_fee_fixed=payload.processor_fee,
            actual_fx_rate=payload.actual_fx_rate,
            target_currency=payload.target_currency,
        )
        net_usd = calc.net_payout_amount
        if net_local is None and payload.target_currency:
            net_local = calc.bank_deposit_amount

    record = UserEarningRecord(
        user_id=current_user.id,
        project_title=payload.project_title,
        client_name=payload.client_name,
        platform=payload.platform,
        job_id=payload.job_id,
        currency=payload.currency.upper(),
        gross_amount=payload.gross_amount,
        platform_fee_paid=payload.contract_service_fee,
        tax_on_fee_paid=payload.fee_tax,
        withholding_paid=payload.withholding_tax,
        withdrawal_fee_paid=payload.withdrawal_fee,
        processor_fee_paid=payload.processor_fee,
        net_received_usd=net_usd,
        net_received_local=net_local,
        target_currency=payload.target_currency,
        actual_fx_rate=payload.actual_fx_rate,
        invoice_status=payload.invoice_status,
        paid_at=payload.payment_date,
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "earning": {
            "id": str(record.id),
            "project_title": record.project_title,
            "client_name": record.client_name,
            "platform": record.platform,
            "currency": record.currency,
            "gross_amount": record.gross_amount,
            "net_received_in_bank": record.net_received_local or record.net_received_usd,
            "invoice_status": record.invoice_status,
        },
    }


@router.put("/earnings/{earning_id}")
async def update_user_earning(
    earning_id: str,
    payload: UserEarningUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Update status, amounts, or payment confirmation of an earning record."""
    clean_id = earning_id.replace("earn_", "")
    int_id = int(clean_id) if clean_id.isdigit() else -1

    stmt = select(UserEarningRecord).where(
        UserEarningRecord.id == int_id,
        UserEarningRecord.user_id == current_user.id,
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Earning record not found")

    update_dict = payload.model_dump(exclude_unset=True)
    if "contract_service_fee" in update_dict:
        record.platform_fee_paid = update_dict["contract_service_fee"]
    if "fee_tax" in update_dict:
        record.tax_on_fee_paid = update_dict["fee_tax"]
    if "withholding_tax" in update_dict:
        record.withholding_paid = update_dict["withholding_tax"]
    if "withdrawal_fee" in update_dict:
        record.withdrawal_fee_paid = update_dict["withdrawal_fee"]
    if "processor_fee" in update_dict:
        record.processor_fee_paid = update_dict["processor_fee"]
    if "payment_date" in update_dict:
        record.paid_at = update_dict["payment_date"]
    if "net_payout_amount" in update_dict:
        record.net_received_usd = update_dict["net_payout_amount"]
    if "net_received_in_bank" in update_dict:
        record.net_received_local = update_dict["net_received_in_bank"]

    for k in ("project_title", "client_name", "platform", "currency", "gross_amount", "actual_fx_rate", "invoice_status", "notes"):
        if k in update_dict and update_dict[k] is not None:
            setattr(record, k, update_dict[k])

    record.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(record)

    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "earning_id": str(record.id),
        "invoice_status": record.invoice_status,
        "updated": True,
    }


@router.delete("/earnings/{earning_id}")
async def delete_user_earning(
    earning_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Delete a user earning record."""
    clean_id = earning_id.replace("earn_", "")
    int_id = int(clean_id) if clean_id.isdigit() else -1

    stmt = select(UserEarningRecord).where(
        UserEarningRecord.id == int_id,
        UserEarningRecord.user_id == current_user.id,
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Earning record not found")

    await session.delete(record)
    await session.commit()

    return {"status": "deleted", "earning_id": earning_id}


@router.get("/earnings/export")
async def export_user_earnings_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Download sanitized CSV of confirmed won projects and receipts.
    
    Contains NO bank credentials, NO account numbers, NO sensitive financial keys.
    """
    stmt = select(UserEarningRecord).where(
        UserEarningRecord.user_id == current_user.id
    ).order_by(UserEarningRecord.created_at.desc())
    res = await session.execute(stmt)
    records = res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Project Title",
        "Client",
        "Platform",
        "Status",
        "Currency",
        "Gross Amount",
        "Platform Fee",
        "Tax On Fee",
        "Withholding Tax (TDS Credit)",
        "Withdrawal Fee",
        "Processor Fee",
        "Actual FX Rate",
        "Net In Bank",
        "Payment Date",
        "Created At",
        "Notes",
    ])

    for r in records:
        writer.writerow([
            r.id,
            r.project_title,
            r.client_name or "",
            r.platform,
            r.invoice_status,
            r.currency,
            f"{r.gross_amount:.2f}",
            f"{r.platform_fee_paid:.2f}",
            f"{r.tax_on_fee_paid:.2f}",
            f"{r.withholding_paid:.2f}",
            f"{r.withdrawal_fee_paid:.2f}",
            f"{r.processor_fee_paid:.2f}",
            f"{r.actual_fx_rate:.4f}" if r.actual_fx_rate else "",
            f"{(r.net_received_local or r.net_received_usd):.2f}",
            r.paid_at.strftime("%Y-%m-%d") if r.paid_at else "",
            r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            r.notes or "",
        ])

    csv_data = output.getvalue()
    filename = f"earnings_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
