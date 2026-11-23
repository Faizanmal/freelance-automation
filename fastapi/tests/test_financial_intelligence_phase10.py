"""Comprehensive unit and integration test suite for Phase 10:
Freelancer Financial Intelligence and Transparent Earnings Calculator.

Gate Criteria Verified:
1. Exact reference regression fixture ($800 gross, 10% fee, 18% GST, 0.1% TDS, $0.99 withdrawal,
   91.5069 offered FX, 94.2455 benchmark FX -> 703.81 USD, 64,403.47 computed INR vs 64,403.44 quote).
2. Inverse net-to-gross calculator round-trip (achieves target within 0.01 tolerance).
3. Deduction allocation: permanent platform costs vs potentially recoverable tax credits.
4. Edge conditions: zero/negative inputs, 0% fee, fixed fees above gross balance, 0-decimal currency (JPY).
5. Withdrawal frequency simulations (daily, weekly, biweekly, monthly annual drag).
6. FX transparency: benchmark vs offered spread cost, timestamp, outage state, manual rate overrides.
7. Verified platform fee templates (primary source links, effective dates, user custom overrides).
8. User earnings workspace: confirmed won projects CRUD, strictly separated cash received from pipeline.
9. Security & Privacy: zero sensitive bank credentials or account numbers requested or stored.
10. Downloadable sanitized CSV export.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import get_current_user
from app.main import create_app
from backend.application.services.fee_templates import FeeTemplateService, SYSTEM_FEE_TEMPLATES
from backend.application.services.financial_calculator import (
    CalculationBreakdown,
    FinancialCalculator,
    InverseQuoteResult,
)
from backend.application.services.fx_service import FxService
from database.core.base import Base
from database.core.session import get_db
from database.models.finance import FeeTemplateRecord, FxRateCacheRecord, UserEarningRecord
from database.models.user import User


@pytest_asyncio.fixture
async def test_db_session():
    """Isolated in-memory SQLite database session for hermetic testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def test_user() -> User:
    return User(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email="freelancer@example.com",
        full_name="Test Freelancer",
        hashed_password="test_hashed_pwd",
        is_active=True,
        account_role="freelancer",
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. Core Calculator Unit Tests & Reference Regression Fixture
# ---------------------------------------------------------------------------

def test_reference_regression_fixture_800():
    """Verify the exact reference regression fixture from the requirement specification.
    
    Inputs:
      Gross: $800.00
      Contract service fee: 10% ($80.00)
      Tax on fee: 18% ($14.40)
      Withholding tax (TDS): 0.1% ($0.80)
      Withdrawal fee: 1 x $0.99 ($0.99)
      Offered FX rate: 91.5069 INR/USD
      Benchmark FX rate: 94.2455 INR/USD
      Reported bank quote: 64,403.44 INR
      
    Expected:
      Net USD = 703.81
      Computed INR = 64,403.47
      Reconciliation discrepancy = 0.03 INR (accepted within tolerance)
      Recoverable tax credit = $0.80
      Permanent platform costs = $95.39 ($80.00 + $14.40 + $0.99)
    """
    calc = FinancialCalculator.calculate_gross_to_net(
        gross_amount=800.0,
        currency="USD",
        contract_service_fee_pct=10.0,
        contract_service_fee_fixed=0.0,
        fee_tax_pct=18.0,
        withholding_tax_pct=0.1,
        withholding_tax_base="gross",
        withdrawal_fee=0.99,
        withdrawal_count=1,
        processor_fee_pct=0.0,
        processor_fee_fixed=0.0,
        other_expenses=0.0,
        benchmark_fx_rate=94.2455,
        actual_fx_rate=91.5069,
        target_currency="INR",
        reported_bank_quote=64403.44,
    )

    # Net USD check
    assert calc.gross_amount == 800.0
    assert calc.contract_service_fee == 80.00
    assert calc.fee_tax == 14.40
    assert calc.withholding_tax == 0.80
    assert calc.withdrawal_fee_total == 0.99
    assert calc.net_payout_amount == 703.81

    # Currency conversion & rounding
    assert calc.bank_deposit_amount == 64403.47
    assert calc.reported_bank_quote == 64403.44
    assert calc.reconciliation_discrepancy == 0.03
    assert calc.reconciliation_status == "reconciled_within_tolerance"

    # Category separation: Permanent vs Recoverable
    assert calc.recoverable_credits == 0.80
    assert calc.permanent_costs == 95.39
    assert calc.total_deductions_base == 96.19

    # Benchmark spread cost
    assert calc.benchmark_bank_deposit == 66330.93
    assert calc.fx_spread_cost_total == 1927.46  # 66330.93 - 64403.47


def test_inverse_solver_round_trip():
    """Verify net-to-gross inverse calculator guarantees exact target bank deposit."""
    # Target: Receive exactly $703.81 in USD
    quote = FinancialCalculator.calculate_net_to_gross(
        target_net_amount=703.81,
        currency="USD",
        contract_service_fee_pct=10.0,
        fee_tax_pct=18.0,
        withholding_tax_pct=0.1,
        withholding_tax_base="gross",
        withdrawal_fee=0.99,
        withdrawal_count=1,
    )

    assert quote.meets_target is True
    assert quote.required_gross_amount == 800.0
    assert quote.verification_net_deposit == 703.81
    assert abs(quote.rounding_discrepancy) <= 0.01

    # Hourly rate suggestion test
    quote_hourly = FinancialCalculator.calculate_net_to_gross(
        target_net_amount=1000.0,
        currency="USD",
        contract_service_fee_pct=10.0,
        hourly_hours=20.0,
    )
    assert quote_hourly.suggested_hourly_rate is not None
    assert quote_hourly.suggested_hourly_rate > 0
    expected_hourly = round(quote_hourly.required_gross_amount / 20.0, 2)
    assert quote_hourly.suggested_hourly_rate == expected_hourly


def test_zero_and_negative_inputs():
    """Verify boundary conditions: zero gross, negative gross, zero fee."""
    calc_zero = FinancialCalculator.calculate_gross_to_net(
        gross_amount=0.0,
        currency="USD",
        contract_service_fee_pct=10.0,
        withdrawal_fee=5.0,
    )
    assert calc_zero.gross_amount == 0.0
    assert calc_zero.net_payout_amount == 0.0
    assert calc_zero.bank_deposit_amount == 0.0

    calc_deficit = FinancialCalculator.calculate_gross_to_net(
        gross_amount=10.0,
        currency="USD",
        withdrawal_fee=25.0,
    )
    assert calc_deficit.net_payout_amount == 0.0
    assert calc_deficit.bank_deposit_amount == 0.0

    calc_no_fee = FinancialCalculator.calculate_gross_to_net(
        gross_amount=500.0,
        currency="USD",
        contract_service_fee_pct=0.0,
    )
    assert calc_no_fee.contract_service_fee == 0.0
    assert calc_no_fee.net_payout_amount == 500.0


def test_jpy_zero_decimal_currency():
    """Verify currencies with 0 minor unit precision (e.g. JPY) round to whole units."""
    calc_jpy = FinancialCalculator.calculate_gross_to_net(
        gross_amount=100000.0,
        currency="JPY",
        contract_service_fee_pct=10.0,
        fee_tax_pct=10.0,
        withdrawal_fee=200.0,
    )
    assert calc_jpy.currency == "JPY"
    assert calc_jpy.contract_service_fee == 10000.0
    assert calc_jpy.fee_tax == 1000.0
    assert calc_jpy.net_payout_amount == 88800.0
    assert float(calc_jpy.bank_deposit_amount).is_integer()


def test_multi_withdrawal_frequency_simulation():
    """Verify withdrawal frequency simulation correctly measures annual fee drag."""
    sim = FinancialCalculator.simulate_withdrawal_frequencies(
        annual_gross=60000.0,
        currency="USD",
        withdrawal_fee=2.00,
    )

    assert "daily" in sim
    assert "weekly" in sim
    assert "biweekly" in sim
    assert "monthly" in sim
    assert "quarterly" in sim

    # Daily: 250 x $2 = $500
    assert sim["daily"]["annual_withdrawal_fees"] == 500.00
    # Monthly: 12 x $2 = $24
    assert sim["monthly"]["annual_withdrawal_fees"] == 24.00
    assert sim["daily"]["fee_drag_pct"] > sim["monthly"]["fee_drag_pct"]


# ---------------------------------------------------------------------------
# 2. FX Service Tests (Benchmarks, Outage, Manual Overrides)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fx_service_reference_and_manual_override(test_db_session: AsyncSession):
    fx_svc = FxService(test_db_session)

    # 1. Identity conversion
    res_id = await fx_svc.get_fx_rate("USD", "USD")
    assert res_id["benchmark_rate"] == 1.0
    assert res_id["offered_rate"] == 1.0
    assert res_id["is_outage"] is False

    # 2. Manual rate override
    res_manual = await fx_svc.get_fx_rate("USD", "INR", manual_rate=92.5)
    assert res_manual["benchmark_rate"] == 92.5
    assert res_manual["offered_rate"] == 92.5
    assert res_manual["rate_type"] == "manual_override"

    # 3. Known reference pair (USD -> EUR)
    res_pair = await fx_svc.get_fx_rate("USD", "EUR")
    assert res_pair["benchmark_rate"] > 0
    assert res_pair["offered_rate"] > 0
    assert res_pair["spread_pct"] > 0
    assert res_pair["is_outage"] is False

    # 4. Unknown pair (fallback outage)
    res_unknown = await fx_svc.get_fx_rate("XYZ", "ABC")
    assert res_unknown["is_outage"] is True
    assert res_unknown["rate_type"] == "outage_fallback"


# ---------------------------------------------------------------------------
# 3. Fee Template Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fee_templates_system_and_custom(test_user: User, test_db_session: AsyncSession):
    svc = FeeTemplateService(test_db_session)

    # 1. Non-marketplace system templates exist (Stripe + Custom)
    sys_templates = svc.get_system_templates()
    assert len(sys_templates) >= 2
    platforms = {t["platform"] for t in sys_templates}
    assert "upwork" not in platforms
    assert "fiverr" not in platforms
    assert "freelancer" not in platforms
    assert "direct_stripe" in platforms
    assert "custom" in platforms
    stripe_tpl = next(t for t in sys_templates if t["platform"] == "direct_stripe")
    assert stripe_tpl["processor_fee_pct"] == 2.9
    assert "http" in stripe_tpl["source_url"]

    # 2. Create custom template for user
    custom = await svc.create_custom_template(
        user_id=test_user.id,
        data={
            "template_name": "Direct Retainer",
            "platform": "direct",
            "contract_service_fee_pct": 0.0,
            "processor_fee_pct": 2.5,
            "processor_fee_fixed": 0.25,
        },
    )
    assert custom.slug.startswith(f"user_{test_user.id[:8]}")
    assert custom.name == "Direct Retainer"

    # 3. List templates for user includes system + custom
    user_list = await svc.list_templates(user_id=test_user.id)
    assert any(t["slug"] == custom.slug for t in user_list)

    # 4. Delete custom template
    deleted = await svc.delete_custom_template(custom.id, test_user.id)
    assert deleted is True


# ---------------------------------------------------------------------------
# 4. API Endpoints Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_calculate_gross_to_net(test_db_session: AsyncSession):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/finance/calculate",
            json={
                "gross_amount": 800.0,
                "currency": "USD",
                "target_currency": "INR",
                "contract_service_fee_pct": 10.0,
                "fee_tax_pct": 18.0,
                "withholding_tax_pct": 0.1,
                "withholding_tax_base": "gross",
                "withdrawal_fee": 0.99,
                "actual_fx_rate": 91.5069,
                "benchmark_fx_rate": 94.2455,
                "reported_bank_quote": 64403.44,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "disclaimer" in data
        assert data["calculation"]["net_payout_amount"] == 703.81
        assert data["calculation"]["bank_deposit_amount"] == 64403.47
        assert data["calculation"]["reconciliation_status"] == "reconciled_within_tolerance"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_calculate_net_to_gross_inverse(test_db_session: AsyncSession):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/finance/calculate/inverse",
            json={
                "target_net_amount": 703.81,
                "currency": "USD",
                "contract_service_fee_pct": 10.0,
                "fee_tax_pct": 18.0,
                "withholding_tax_pct": 0.1,
                "withdrawal_fee": 0.99,
                "hourly_hours": 20.0,
            },
        )
        assert resp.status_code == 200
        quote = resp.json()["quote"]
        assert quote["meets_target"] is True
        assert quote["required_gross_amount"] == 800.0
        assert quote["suggested_hourly_rate"] == 40.0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_compare_scenarios(test_db_session: AsyncSession):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/finance/calculate/compare",
            json={
                "gross_amount": 1000.0,
                "currency": "USD",
                "scenarios": [
                    {
                        "name": "Upwork (10%)",
                        "contract_service_fee_pct": 10.0,
                        "withdrawal_fee": 0.99,
                    },
                    {
                        "name": "Fiverr (20%)",
                        "contract_service_fee_pct": 20.0,
                        "withdrawal_fee": 0.0,
                    },
                    {
                        "name": "Direct Stripe (2.9% + $0.30)",
                        "contract_service_fee_pct": 0.0,
                        "processor_fee_pct": 2.9,
                        "processor_fee_fixed": 0.30,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["scenarios"]) == 3
        stripe_sc = next(s for s in data["scenarios"] if "Stripe" in s.get("name", s.get("scenario_name", "")))
        fiverr_sc = next(s for s in data["scenarios"] if "Fiverr" in s.get("name", s.get("scenario_name", "")))
        assert stripe_sc["bank_deposit"] > fiverr_sc["bank_deposit"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_user_earnings_crud_and_csv_export(test_user: User, test_db_session: AsyncSession):
    app = create_app()

    # Override dependencies
    app.dependency_overrides[get_db] = lambda: test_db_session
    app.dependency_overrides[get_current_user] = lambda: test_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a paid earning
        create_resp = await client.post(
            "/api/v1/finance/earnings",
            json={
                "project_title": "Enterprise Microservice",
                "client_name": "Acme Corp",
                "platform": "upwork",
                "currency": "USD",
                "gross_amount": 2000.0,
                "contract_service_fee": 200.0,
                "withdrawal_fee": 0.99,
                "net_received_in_bank": 1799.01,
                "invoice_status": "paid",
            },
        )
        assert create_resp.status_code == 201
        earning_id = create_resp.json()["earning"]["id"]

        # 2. Create an unpaid draft (pipeline)
        draft_resp = await client.post(
            "/api/v1/finance/earnings",
            json={
                "project_title": "Mobile App UI",
                "client_name": "Beta Labs",
                "platform": "direct",
                "currency": "USD",
                "gross_amount": 1500.0,
                "invoice_status": "invoiced",
            },
        )
        assert draft_resp.status_code == 201
        draft_id = draft_resp.json()["earning"]["id"]

        # 3. List earnings & verify cash received is strictly separated from pipeline
        list_resp = await client.get("/api/v1/finance/earnings")
        assert list_resp.status_code == 200
        summary = list_resp.json()["summary"]
        assert summary["cash_received"] == 1799.01
        assert summary["pipeline_estimated_gross"] == 1500.0  # pipeline NOT in cash_received

        # 4. Export CSV
        csv_resp = await client.get("/api/v1/finance/earnings/export")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        csv_text = csv_resp.text
        assert "Enterprise Microservice" in csv_text
        assert "Mobile App UI" in csv_text
        # Security assertion: ensure NO bank account credentials or account numbers exist
        assert "account_number" not in csv_text.lower()
        assert "routing_number" not in csv_text.lower()
        assert "iban" not in csv_text.lower()

        # 5. Delete earning
        del_resp = await client.delete(f"/api/v1/finance/earnings/{draft_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

    app.dependency_overrides.clear()
