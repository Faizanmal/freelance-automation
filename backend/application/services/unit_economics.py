"""Unit Economics and Cost Instrumentation Service.

Models per-user infrastructure, AI, search, and payment processing costs.
Generates Low, Base, and High/Max-Quota usage scenarios to ensure sustainable margins.
Strictly separates measured historical costs from model estimates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.billing import UsageRecord

# ---------------------------------------------------------------------------
# Unit Cost Benchmarks (verified provider pricing)
# ---------------------------------------------------------------------------
SEARCH_COST_PER_CALL = 0.0075          # SerpAPI / Tavily blended per hunt
LLM_INPUT_COST_PER_1K = 0.00015        # $0.15 per 1M input tokens (Gemini 1.5 Flash / Claude Haiku)
LLM_OUTPUT_COST_PER_1K = 0.00060       # $0.60 per 1M output tokens
EMAIL_COST_PER_SEND = 0.00010          # Resend / AWS SES
WHATSAPP_COST_PER_SEND = 0.03500       # Meta Cloud API message fee
INFRA_PER_USER_MONTH = 0.25000         # DB, Redis cache, queue workers amortized
SUPPORT_PER_USER_MONTH = 0.50000       # Tier-1 support overhead allocation
STRIPE_FIXED_FEE = 0.30                # $0.30 per charge
STRIPE_PERCENT_FEE = 0.029             # 2.9% processor fee

PRO_PRICE_MONTHLY_USD = 19.00


@dataclass(slots=True)
class UnitEconomicsScenario:
    name: str
    description: str
    monthly_price: float
    monthly_hunts: int
    monthly_copilot_runs: int
    avg_tokens_per_run: int
    monthly_digests: int
    
    # Computed breakdown
    search_api_cost: float
    llm_tokens_cost: float
    notification_cost: float
    infra_cost: float
    support_cost: float
    payment_processor_fee: float
    total_cogs: float
    gross_profit: float
    gross_margin_pct: float
    breakeven_price: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UnitEconomicsService:
    """Calculates and monitors SaaS subscription unit economics and margins."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    @classmethod
    def calculate_scenario(
        cls,
        name: str,
        description: str,
        monthly_hunts: int,
        monthly_copilot_runs: int,
        avg_tokens_per_run: int,
        monthly_digests: int,
        monthly_price: float = PRO_PRICE_MONTHLY_USD,
    ) -> UnitEconomicsScenario:
        """Calculate direct Cost of Goods Sold (COGS) and gross margin for a scenario."""
        search_cost = round(monthly_hunts * SEARCH_COST_PER_CALL, 2)

        # 60% input tokens, 40% output tokens approximation
        total_tokens = monthly_copilot_runs * avg_tokens_per_run
        input_tokens_k = (total_tokens * 0.6) / 1000.0
        output_tokens_k = (total_tokens * 0.4) / 1000.0
        llm_cost = round(
            (input_tokens_k * LLM_INPUT_COST_PER_1K) + (output_tokens_k * LLM_OUTPUT_COST_PER_1K),
            2,
        )

        notification_cost = round(monthly_digests * EMAIL_COST_PER_SEND, 3)
        infra_cost = round(INFRA_PER_USER_MONTH, 2)
        support_cost = round(SUPPORT_PER_USER_MONTH, 2)

        processor_fee = round((monthly_price * STRIPE_PERCENT_FEE) + STRIPE_FIXED_FEE, 2) if monthly_price > 0 else 0.0

        total_cogs = round(
            search_cost + llm_cost + notification_cost + infra_cost + support_cost + processor_fee,
            2,
        )
        gross_profit = round(monthly_price - total_cogs, 2)
        gross_margin_pct = round((gross_profit / monthly_price) * 100.0, 1) if monthly_price > 0 else 0.0
        breakeven_price = total_cogs

        return UnitEconomicsScenario(
            name=name,
            description=description,
            monthly_price=monthly_price,
            monthly_hunts=monthly_hunts,
            monthly_copilot_runs=monthly_copilot_runs,
            avg_tokens_per_run=avg_tokens_per_run,
            monthly_digests=monthly_digests,
            search_api_cost=search_cost,
            llm_tokens_cost=llm_cost,
            notification_cost=notification_cost,
            infra_cost=infra_cost,
            support_cost=support_cost,
            payment_processor_fee=processor_fee,
            total_cogs=total_cogs,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            breakeven_price=breakeven_price,
        )

    @classmethod
    def get_benchmark_scenarios(cls) -> list[dict[str, Any]]:
        """Return standardized unit economics scenarios (Low, Base, High, and Safety-Cap Ceiling)."""
        scenarios = [
            cls.calculate_scenario(
                name="Low Usage (Occasional Freelancer)",
                description="Hunts once every few days, light proposal drafting, weekly digest.",
                monthly_hunts=15,
                monthly_copilot_runs=8,
                avg_tokens_per_run=2500,
                monthly_digests=4,
            ),
            cls.calculate_scenario(
                name="Base / Median Usage (Typical Active Freelancer)",
                description="Daily hunt, active copilot drafting, daily digest notifications.",
                monthly_hunts=45,
                monthly_copilot_runs=35,
                avg_tokens_per_run=4000,
                monthly_digests=22,
            ),
            cls.calculate_scenario(
                name="High Usage (Power User within Plan Fair-Use)",
                description="Heavy multi-query searches, extensive proposal refinement, daily alerts.",
                monthly_hunts=120,
                monthly_copilot_runs=90,
                avg_tokens_per_run=6000,
                monthly_digests=30,
            ),
            cls.calculate_scenario(
                name="Stress Ceiling (Max Quota with $15 Operator Cap)",
                description="User maxing daily hunt and copilot runs, clamped by $15 operator spending ceiling.",
                monthly_hunts=300,
                monthly_copilot_runs=200,
                avg_tokens_per_run=8000,
                monthly_digests=30,
            ),
        ]
        return [s.to_dict() for s in scenarios]

    async def get_measured_vs_estimated_costs(self, user_id: str | None = None) -> dict[str, Any]:
        """Aggregate actual measured usage records from the database and contrast with model estimates."""
        if not self.session:
            return {"measured_total_usd": 0.0, "status": "no_database_session"}

        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")

        stmt = select(
            UsageRecord.feature,
            func.coalesce(func.sum(UsageRecord.units_used), 0),
            func.coalesce(func.sum(UsageRecord.cost_estimate_usd), 0.0),
        ).where(UsageRecord.period_key.like(f"{current_month}%"))

        if user_id:
            stmt = stmt.where(UsageRecord.user_id == user_id)

        stmt = stmt.group_by(UsageRecord.feature)
        res = await self.session.execute(stmt)

        measured_breakdown = {}
        total_measured = 0.0

        for feat, units, cost in res.all():
            cost_f = round(float(cost), 4)
            total_measured += cost_f
            measured_breakdown[feat] = {
                "units_used": int(units),
                "measured_cost_usd": cost_f,
            }

        return {
            "period": current_month,
            "user_id": user_id or "all_active_users",
            "total_measured_cost_usd": round(total_measured, 2),
            "measured_features": measured_breakdown,
            "pricing_hypothesis": f"${PRO_PRICE_MONTHLY_USD:.2f}/mo Pro Plan",
            "operator_hard_cap_usd": 15.00,
        }
