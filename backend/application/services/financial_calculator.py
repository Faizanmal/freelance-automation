"""Freelancer Financial Intelligence and Transparent Earnings Calculator.

Informational planning tool — not tax or financial advice. Does not hold or move money.
Uses Decimal arithmetic and currency-aware rounding server-side to prevent floating-point discrepancies.
Distinguishes actual bank deposit, permanent platform/processing costs, and potentially recoverable tax credits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Literal

# Standard minor-unit decimal places for currencies
CURRENCY_DECIMALS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "INR": 2,
    "CAD": 2,
    "AUD": 2,
    "SGD": 2,
    "JPY": 0,
    "KRW": 0,
    "BRL": 2,
    "MXN": 2,
}

LEGAL_DISCLAIMER: str = (
    "Informational calculation only — not financial, accounting, or tax advice. "
    "Antigravity does not custody or transfer funds. Withholding tax credits depend on user tax filing status. "
    "Exchange rates and fee policies are subject to provider updates and rounding variations."
)


def to_decimal(val: Any, default: str = "0.00") -> Decimal:
    """Safely converts float/int/str/None to Decimal."""
    if val is None or val == "":
        return Decimal(default)
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def round_currency(amount: Decimal, currency: str = "USD") -> Decimal:
    """Rounds a Decimal amount to the official minor unit of the currency using ROUND_HALF_UP."""
    digits = CURRENCY_DECIMALS.get(currency.upper(), 2)
    exponent = Decimal("1") if digits == 0 else Decimal("0." + "0" * digits)
    return amount.quantize(exponent, rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class CalculationInput:
    gross_amount: float
    currency: str = "USD"
    contract_service_fee_pct: float = 0.0
    contract_service_fee_fixed: float = 0.0
    tax_on_fee_pct: float = 0.0
    withholding_tax_pct: float = 0.0
    withholding_base: Literal["gross", "fee"] = "gross"
    withdrawal_fee: float = 0.0
    withdrawal_count: int = 1
    processor_charge_pct: float = 0.0
    processor_charge_fixed: float = 0.0
    other_expenses: float = 0.0
    benchmark_fx_rate: float | None = None
    actual_conversion_rate: float | None = None
    target_currency: str | None = None
    reported_bank_quote: float | None = None
    hours_logged: float | None = None


@dataclass(slots=True)
class FeeBreakdownItem:
    name: str
    category: Literal["permanent_cost", "recoverable_credit", "gross", "net_deposit"]
    amount: float
    currency: str
    description: str
    is_recoverable: bool = False


@dataclass(slots=True)
class CalculationResult:
    gross_amount: float
    currency: str
    service_fee: float
    tax_on_service_fee: float
    withholding_tax: float
    processor_charges: float
    withdrawal_fees: float
    other_expenses: float
    total_deductions_base: float
    net_amount_base: float
    # Target Currency & FX Details
    target_currency: str | None
    actual_conversion_rate: float | None
    benchmark_fx_rate: float | None
    net_target_currency: float | None
    benchmark_net_target_currency: float | None
    fx_spread_cost_target: float | None
    fx_spread_cost_base: float | None
    # Categorization
    permanent_costs_base: float
    recoverable_credits_base: float
    actual_deposit_base: float
    actual_deposit_target: float | None
    # Hourly & Effective
    hours_logged: float | None
    effective_hourly_rate_base: float | None
    effective_take_home_pct: float
    # Discrepancy & Reconciliation
    reported_bank_quote: float | None
    reconciliation_discrepancy: float | None
    within_tolerance: bool
    breakdown: list[dict[str, Any]]
    disclaimer: str = LEGAL_DISCLAIMER

    # Compatibility properties
    @property
    def contract_service_fee(self) -> float:
        return self.service_fee

    @property
    def fee_tax(self) -> float:
        return self.tax_on_service_fee

    @property
    def withdrawal_fee_total(self) -> float:
        return self.withdrawal_fees

    @property
    def processor_fee_total(self) -> float:
        return self.processor_charges

    @property
    def net_payout_amount(self) -> float:
        return self.net_amount_base

    @property
    def bank_deposit_amount(self) -> float:
        return self.actual_deposit_target if self.actual_deposit_target is not None else self.actual_deposit_base

    @property
    def permanent_costs(self) -> float:
        return self.permanent_costs_base

    @property
    def recoverable_credits(self) -> float:
        return self.recoverable_credits_base

    @property
    def fx_spread_cost_total(self) -> float | None:
        return self.fx_spread_cost_target

    @property
    def benchmark_bank_deposit(self) -> float | None:
        return self.benchmark_net_target_currency

    @property
    def reconciliation_status(self) -> str:
        if self.reported_bank_quote is None:
            return "not_provided"
        if self.reconciliation_discrepancy == 0.0:
            return "reconciled_exact"
        if self.within_tolerance:
            return "reconciled_within_tolerance"
        return "discrepancy_exceeded"

    def to_dict(self) -> dict[str, Any]:
        """Convert calculation breakdown to API-friendly dictionary."""
        effective_cost_pct = 0.0
        if self.gross_amount > 0:
            effective_cost_pct = round((self.permanent_costs / self.gross_amount) * 100.0, 2)

        itemized = []
        for b in self.breakdown:
            amt = float(b["amount"])
            pct = round((amt / self.gross_amount) * 100.0, 2) if self.gross_amount > 0 else 0.0
            itemized.append({
                "name": b["name"],
                "code": b["name"].lower().replace(" ", "_"),
                "amount_base": amt,
                "amount_target": round(amt * (self.actual_conversion_rate or 1.0), 2),
                "pct_of_gross": pct,
                "category": b["category"],
                "notes": b["description"],
            })

        return {
            "gross_amount": self.gross_amount,
            "currency": self.currency,
            "target_currency": self.target_currency or self.currency,
            "contract_service_fee": self.service_fee,
            "fee_tax": self.tax_on_service_fee,
            "withholding_tax": self.withholding_tax,
            "withdrawal_fee_total": self.withdrawal_fees,
            "processor_fee_total": self.processor_charges,
            "other_expenses": self.other_expenses,
            "total_deductions_base": self.total_deductions_base,
            "permanent_costs": self.permanent_costs,
            "recoverable_credits": self.recoverable_credits,
            "net_payout_amount": self.net_payout_amount,
            "bank_deposit_amount": self.bank_deposit_amount,
            "benchmark_bank_deposit": self.benchmark_bank_deposit,
            "fx_spread_cost_total": self.fx_spread_cost_total,
            "reported_bank_quote": self.reported_bank_quote,
            "reconciliation_discrepancy": self.reconciliation_discrepancy,
            "reconciliation_status": self.reconciliation_status,
            "effective_take_home_rate_pct": self.effective_take_home_pct,
            "effective_total_cost_pct": effective_cost_pct,
            "itemized_deductions": itemized,
            "disclaimer": self.disclaimer,
        }


# Alias for backward compatibility
CalculationBreakdown = CalculationResult


@dataclass(slots=True)
class InverseQuoteResult:
    target_net_amount: float
    required_gross_amount: float
    currency: str
    target_currency: str
    hourly_hours: float | None
    suggested_hourly_rate: float | None
    verification_net_deposit: float
    rounding_discrepancy: float
    meets_target: bool
    deduction_breakdown: dict[str, float]
    disclaimer: str = LEGAL_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinancialCalculator:
    """Performs deterministic, currency-aware gross-to-net and net-to-gross calculations."""

    @classmethod
    def calculate_gross_to_net(
        cls,
        inp: CalculationInput | None = None,
        **kwargs: Any,
    ) -> CalculationResult:
        if inp is None:
            # Map keyword argument aliases
            gross = kwargs.get("gross_amount", 0.0)
            currency = kwargs.get("currency", "USD")
            target_curr = kwargs.get("target_currency")
            fee_pct = kwargs.get("contract_service_fee_pct", 0.0)
            fee_fixed = kwargs.get("contract_service_fee_fixed", 0.0)
            tax_pct = kwargs.get("fee_tax_pct", kwargs.get("tax_on_fee_pct", 0.0))
            withholding_pct = kwargs.get("withholding_tax_pct", 0.0)
            withholding_base = kwargs.get("withholding_tax_base", kwargs.get("withholding_base", "gross"))
            withdrawal_fee = kwargs.get("withdrawal_fee", 0.0)
            withdrawal_cnt = kwargs.get("withdrawal_count", 1)
            proc_pct = kwargs.get("processor_fee_pct", kwargs.get("processor_charge_pct", 0.0))
            proc_fixed = kwargs.get("processor_fee_fixed", kwargs.get("processor_charge_fixed", 0.0))
            other_exp = kwargs.get("other_expenses", 0.0)
            bench_fx = kwargs.get("benchmark_fx_rate")
            act_fx = kwargs.get("actual_fx_rate", kwargs.get("actual_conversion_rate"))
            bank_quote = kwargs.get("reported_bank_quote")
            hours = kwargs.get("hours_logged")

            inp = CalculationInput(
                gross_amount=gross,
                currency=currency,
                contract_service_fee_pct=fee_pct,
                contract_service_fee_fixed=fee_fixed,
                tax_on_fee_pct=tax_pct,
                withholding_tax_pct=withholding_pct,
                withholding_base=withholding_base,
                withdrawal_fee=withdrawal_fee,
                withdrawal_count=withdrawal_cnt,
                processor_charge_pct=proc_pct,
                processor_charge_fixed=proc_fixed,
                other_expenses=other_exp,
                benchmark_fx_rate=bench_fx,
                actual_conversion_rate=act_fx,
                target_currency=target_curr,
                reported_bank_quote=bank_quote,
                hours_logged=hours,
            )

        base_curr = inp.currency.upper()
        target_curr = inp.target_currency.upper() if inp.target_currency else None

        gross_d = max(Decimal("0.00"), to_decimal(inp.gross_amount))
        fee_pct_d = max(Decimal("0.00"), to_decimal(inp.contract_service_fee_pct))
        fee_fixed_d = max(Decimal("0.00"), to_decimal(inp.contract_service_fee_fixed))
        tax_on_fee_pct_d = max(Decimal("0.00"), to_decimal(inp.tax_on_fee_pct))
        withholding_pct_d = max(Decimal("0.00"), to_decimal(inp.withholding_tax_pct))
        proc_pct_d = max(Decimal("0.00"), to_decimal(inp.processor_charge_pct))
        proc_fixed_d = max(Decimal("0.00"), to_decimal(inp.processor_charge_fixed))
        withdrawal_fee_d = max(Decimal("0.00"), to_decimal(inp.withdrawal_fee))
        withdrawal_cnt = max(0, int(inp.withdrawal_count or 1))
        other_exp_d = max(Decimal("0.00"), to_decimal(inp.other_expenses))

        # 1. Platform Service Fee (percentage on gross + fixed)
        service_fee_d = round_currency(
            gross_d * (fee_pct_d / Decimal("100")) + fee_fixed_d, base_curr
        )
        service_fee_d = min(gross_d, service_fee_d)

        # 2. Tax on Service Fee (e.g. 18% GST on platform fee)
        tax_on_fee_d = round_currency(
            service_fee_d * (tax_on_fee_pct_d / Decimal("100")), base_curr
        )

        # 3. Withholding Tax (TDS on gross or fee base; marked as potentially recoverable credit)
        withholding_base_amount = (
            service_fee_d if inp.withholding_base == "fee" else gross_d
        )
        withholding_tax_d = round_currency(
            withholding_base_amount * (withholding_pct_d / Decimal("100")), base_curr
        )

        # 4. Processor Charges (e.g. Stripe/PayPal)
        processor_charges_d = round_currency(
            gross_d * (proc_pct_d / Decimal("100")) + proc_fixed_d, base_curr
        )

        # 5. Withdrawal Fees
        total_withdrawal_fee_d = round_currency(
            withdrawal_fee_d * Decimal(str(withdrawal_cnt)), base_curr
        )

        # 6. Total Deductions & Net Amount in Base Currency
        total_deductions_d = round_currency(
            service_fee_d
            + tax_on_fee_d
            + withholding_tax_d
            + processor_charges_d
            + total_withdrawal_fee_d
            + other_exp_d,
            base_curr,
        )
        net_amount_d = max(Decimal("0.00"), gross_d - total_deductions_d)

        # 7. Permanent Cost vs Recoverable Tax Credit
        permanent_cost_d = round_currency(
            service_fee_d
            + tax_on_fee_d
            + processor_charges_d
            + total_withdrawal_fee_d
            + other_exp_d,
            base_curr,
        )
        recoverable_credit_d = withholding_tax_d

        # 8. Foreign Currency Conversion & Spread
        offered_fx_d = (
            to_decimal(inp.actual_conversion_rate)
            if inp.actual_conversion_rate
            else None
        )
        benchmark_fx_d = (
            to_decimal(inp.benchmark_fx_rate)
            if inp.benchmark_fx_rate
            else None
        )

        net_target_d: Decimal | None = None
        benchmark_net_target_d: Decimal | None = None
        fx_spread_cost_target_d: Decimal | None = None
        fx_spread_cost_base_d: Decimal | None = None

        if target_curr and target_curr != base_curr:
            if offered_fx_d and offered_fx_d > 0:
                net_target_d = round_currency(net_amount_d * offered_fx_d, target_curr)
            if benchmark_fx_d and benchmark_fx_d > 0:
                benchmark_net_target_d = round_currency(
                    net_amount_d * benchmark_fx_d, target_curr
                )
                if net_target_d is not None and benchmark_net_target_d > net_target_d:
                    fx_spread_cost_target_d = benchmark_net_target_d - net_target_d
                    fx_spread_cost_base_d = round_currency(
                        fx_spread_cost_target_d / benchmark_fx_d, base_curr
                    )

        # 9. Effective take-home %
        effective_pct = (
            float(round((net_amount_d / gross_d) * 100, 2)) if gross_d > 0 else 0.0
        )

        # 10. Hourly effective rate
        hours = float(inp.hours_logged or 0)
        eff_hourly = float(round(float(net_amount_d) / hours, 2)) if hours > 0 else None

        # 11. Bank Quote Reconciliation & Minor Unit Tolerance Check
        bank_quote_d = (
            to_decimal(inp.reported_bank_quote)
            if inp.reported_bank_quote is not None
            else None
        )
        discrepancy_d: Decimal | None = None
        within_tolerance = True

        if bank_quote_d is not None:
            comparison_target = (
                net_target_d if net_target_d is not None else net_amount_d
            )
            discrepancy_d = comparison_target - bank_quote_d
            tolerance_threshold = Decimal(
                "0.05"
                if CURRENCY_DECIMALS.get(target_curr or base_curr, 2) == 2
                else "1.00"
            )
            within_tolerance = abs(discrepancy_d) <= tolerance_threshold

        # 12. Structured Breakdown
        breakdown = [
            FeeBreakdownItem(
                name="Gross Billed Amount",
                category="gross",
                amount=float(gross_d),
                currency=base_curr,
                description="Total client invoice amount before any deductions.",
            ),
            FeeBreakdownItem(
                name="Platform Service Fee",
                category="permanent_cost",
                amount=float(service_fee_d),
                currency=base_curr,
                description=f"Platform fee ({inp.contract_service_fee_pct}%"
                + (f" + ${inp.contract_service_fee_fixed}" if inp.contract_service_fee_fixed else "")
                + ").",
            ),
            FeeBreakdownItem(
                name="Tax on Service Fee (GST/VAT)",
                category="permanent_cost",
                amount=float(tax_on_fee_d),
                currency=base_curr,
                description=f"Local consumption tax on platform service fee ({inp.tax_on_fee_pct}%).",
            ),
            FeeBreakdownItem(
                name="Withholding Tax (TDS)",
                category="recoverable_credit",
                amount=float(withholding_tax_d),
                currency=base_curr,
                description=f"Statutory withholding ({inp.withholding_tax_pct}% on {inp.withholding_base}). Potentially claimable as tax credit.",
                is_recoverable=True,
            ),
            FeeBreakdownItem(
                name="Withdrawal Charges",
                category="permanent_cost",
                amount=float(total_withdrawal_fee_d),
                currency=base_curr,
                description=f"{withdrawal_cnt} withdrawal(s) at {inp.withdrawal_fee} {base_curr}.",
            ),
        ]
        if processor_charges_d > 0:
            breakdown.append(
                FeeBreakdownItem(
                    name="Payment Processing Charges",
                    category="permanent_cost",
                    amount=float(processor_charges_d),
                    currency=base_curr,
                    description=f"Payment processor fee ({inp.processor_charge_pct}%).",
                )
            )
        if other_exp_d > 0:
            breakdown.append(
                FeeBreakdownItem(
                    name="Other Expenses",
                    category="permanent_cost",
                    amount=float(other_exp_d),
                    currency=base_curr,
                    description="Additional declared project expenses.",
                )
            )
        if fx_spread_cost_target_d is not None and fx_spread_cost_base_d is not None:
            breakdown.append(
                FeeBreakdownItem(
                    name="FX Conversion Spread (Hidden Cost)",
                    category="permanent_cost",
                    amount=float(fx_spread_cost_base_d),
                    currency=base_curr,
                    description=f"Difference between benchmark rate ({inp.benchmark_fx_rate}) and offered rate ({inp.actual_conversion_rate}).",
                )
            )
        breakdown.append(
            FeeBreakdownItem(
                name="Actual Bank Deposit",
                category="net_deposit",
                amount=float(net_target_d if net_target_d is not None else net_amount_d),
                currency=target_curr or base_curr,
                description="Estimated cash landing in your bank account.",
            )
        )

        return CalculationResult(
            gross_amount=float(gross_d),
            currency=base_curr,
            service_fee=float(service_fee_d),
            tax_on_service_fee=float(tax_on_fee_d),
            withholding_tax=float(withholding_tax_d),
            processor_charges=float(processor_charges_d),
            withdrawal_fees=float(total_withdrawal_fee_d),
            other_expenses=float(other_exp_d),
            total_deductions_base=float(total_deductions_d),
            net_amount_base=float(net_amount_d),
            target_currency=target_curr,
            actual_conversion_rate=float(offered_fx_d) if offered_fx_d else None,
            benchmark_fx_rate=float(benchmark_fx_d) if benchmark_fx_d else None,
            net_target_currency=float(net_target_d) if net_target_d is not None else None,
            benchmark_net_target_currency=(
                float(benchmark_net_target_d) if benchmark_net_target_d is not None else None
            ),
            fx_spread_cost_target=(
                float(fx_spread_cost_target_d) if fx_spread_cost_target_d is not None else None
            ),
            fx_spread_cost_base=(
                float(fx_spread_cost_base_d) if fx_spread_cost_base_d is not None else None
            ),
            permanent_costs_base=float(permanent_cost_d),
            recoverable_credits_base=float(recoverable_credit_d),
            actual_deposit_base=float(net_amount_d),
            actual_deposit_target=float(net_target_d) if net_target_d is not None else None,
            hours_logged=hours if hours > 0 else None,
            effective_hourly_rate_base=eff_hourly,
            effective_take_home_pct=effective_pct,
            reported_bank_quote=float(bank_quote_d) if bank_quote_d is not None else None,
            reconciliation_discrepancy=(
                float(discrepancy_d) if discrepancy_d is not None else None
            ),
            within_tolerance=within_tolerance,
            breakdown=[asdict(item) for item in breakdown],
        )

    @classmethod
    def calculate_net_to_gross(
        cls,
        target_net_amount: float | None = None,
        template: CalculationInput | None = None,
        **kwargs: Any,
    ) -> InverseQuoteResult:
        """Inverse solver: calculates required Gross Quote to achieve desired Net Take-Home."""
        if target_net_amount is None:
            target_net_amount = kwargs.get("target_net", 0.0)

        if template is None:
            currency = kwargs.get("currency", "USD")
            target_curr = kwargs.get("target_currency")
            fee_pct = kwargs.get("contract_service_fee_pct", 0.0)
            fee_fixed = kwargs.get("contract_service_fee_fixed", 0.0)
            tax_pct = kwargs.get("fee_tax_pct", kwargs.get("tax_on_fee_pct", 0.0))
            withholding_pct = kwargs.get("withholding_tax_pct", 0.0)
            withholding_base = kwargs.get("withholding_tax_base", kwargs.get("withholding_base", "gross"))
            withdrawal_fee = kwargs.get("withdrawal_fee", 0.0)
            withdrawal_cnt = kwargs.get("withdrawal_count", 1)
            proc_pct = kwargs.get("processor_fee_pct", kwargs.get("processor_charge_pct", 0.0))
            proc_fixed = kwargs.get("processor_fee_fixed", kwargs.get("processor_charge_fixed", 0.0))
            other_exp = kwargs.get("other_expenses", 0.0)
            act_fx = kwargs.get("actual_fx_rate", kwargs.get("actual_conversion_rate"))
            hours = kwargs.get("hourly_hours", kwargs.get("hours_logged"))

            template = CalculationInput(
                gross_amount=0.0,
                currency=currency,
                contract_service_fee_pct=fee_pct,
                contract_service_fee_fixed=fee_fixed,
                tax_on_fee_pct=tax_pct,
                withholding_tax_pct=withholding_pct,
                withholding_base=withholding_base,
                withdrawal_fee=withdrawal_fee,
                withdrawal_count=withdrawal_cnt,
                processor_charge_pct=proc_pct,
                processor_charge_fixed=proc_fixed,
                other_expenses=other_exp,
                actual_conversion_rate=act_fx,
                target_currency=target_curr,
                hours_logged=hours,
            )

        base_curr = template.currency.upper()
        target_curr = template.target_currency.upper() if template.target_currency else None
        net_goal_d = max(Decimal("0.00"), to_decimal(target_net_amount))

        if target_curr and target_curr != base_curr:
            offered_fx_d = to_decimal(template.actual_conversion_rate)
            if offered_fx_d <= 0:
                raise ValueError("Actual conversion rate must be > 0 to solve from target currency.")
            base_net_goal_d = round_currency(net_goal_d / offered_fx_d, base_curr)
        else:
            base_net_goal_d = net_goal_d

        fee_pct = to_decimal(template.contract_service_fee_pct) / Decimal("100")
        tax_pct = to_decimal(template.tax_on_fee_pct) / Decimal("100")
        withholding_pct = to_decimal(template.withholding_tax_pct) / Decimal("100")
        proc_pct = to_decimal(template.processor_charge_pct) / Decimal("100")

        var_rate = fee_pct * (Decimal("1.00") + tax_pct) + proc_pct
        if template.withholding_base == "gross":
            var_rate += withholding_pct
        else:
            var_rate += fee_pct * withholding_pct

        if var_rate >= Decimal("1.00"):
            raise ValueError("Cumulative percentage deductions meet or exceed 100%; cannot achieve target net.")

        fixed_costs = (
            to_decimal(template.contract_service_fee_fixed)
            + to_decimal(template.processor_charge_fixed)
            + to_decimal(template.withdrawal_fee) * Decimal(str(template.withdrawal_count or 1))
            + to_decimal(template.other_expenses)
        )

        denominator = Decimal("1.00") - var_rate
        approx_gross = round_currency((base_net_goal_d + fixed_costs) / denominator, base_curr)

        # Iterative verification & fine-tuning
        best_gross = approx_gross
        template_copy = CalculationInput(
            gross_amount=float(best_gross),
            currency=template.currency,
            contract_service_fee_pct=template.contract_service_fee_pct,
            contract_service_fee_fixed=template.contract_service_fee_fixed,
            tax_on_fee_pct=template.tax_on_fee_pct,
            withholding_tax_pct=template.withholding_tax_pct,
            withholding_base=template.withholding_base,
            withdrawal_fee=template.withdrawal_fee,
            withdrawal_count=template.withdrawal_count,
            processor_charge_pct=template.processor_charge_pct,
            processor_charge_fixed=template.processor_charge_fixed,
            other_expenses=template.other_expenses,
            actual_conversion_rate=template.actual_conversion_rate,
            target_currency=template.target_currency,
        )

        test_result = cls.calculate_gross_to_net(template_copy)
        test_net = to_decimal(
            test_result.net_target_currency
            if target_curr and target_curr != base_curr
            else test_result.net_amount_base
        )

        step = Decimal("0.01") if CURRENCY_DECIMALS.get(base_curr, 2) == 2 else Decimal("1")
        for _ in range(10):
            if test_net >= net_goal_d:
                break
            best_gross += step
            template_copy.gross_amount = float(best_gross)
            test_result = cls.calculate_gross_to_net(template_copy)
            test_net = to_decimal(
                test_result.net_target_currency
                if target_curr and target_curr != base_curr
                else test_result.net_amount_base
            )

        rounding_diff = float(test_net - net_goal_d)
        meets_target = abs(rounding_diff) <= float(step)

        suggested_hourly = None
        hours_logged = kwargs.get("hourly_hours", template.hours_logged)
        if hours_logged and hours_logged > 0:
            suggested_hourly = round(float(best_gross) / float(hours_logged), 2)

        return InverseQuoteResult(
            target_net_amount=float(net_goal_d),
            required_gross_amount=float(best_gross),
            currency=base_curr,
            target_currency=target_curr or base_curr,
            hourly_hours=hours_logged,
            suggested_hourly_rate=suggested_hourly,
            verification_net_deposit=float(test_net),
            rounding_discrepancy=rounding_diff,
            meets_target=meets_target,
            deduction_breakdown={
                "contract_service_fee": test_result.service_fee,
                "fee_tax": test_result.tax_on_service_fee,
                "withholding_tax": test_result.withholding_tax,
                "withdrawal_fee_total": test_result.withdrawal_fees,
                "processor_fee_total": test_result.processor_charges,
                "other_expenses": test_result.other_expenses,
                "total_deductions_base": test_result.total_deductions_base,
            },
        )

    @classmethod
    def simulate_withdrawal_frequencies(
        cls,
        annual_gross: float,
        currency: str,
        withdrawal_fee: float,
        withdrawal_counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Simulate the annual fee drag and cash arrival of withdrawal frequency choices."""
        counts = withdrawal_counts or {
            "daily": 250,
            "weekly": 52,
            "biweekly": 26,
            "monthly": 12,
            "quarterly": 4,
        }

        ann_gross_d = max(Decimal("0.00"), to_decimal(annual_gross))
        w_fee_d = max(Decimal("0.00"), to_decimal(withdrawal_fee))

        results: dict[str, Any] = {}
        for freq, cnt in counts.items():
            total_fee_d = round_currency(w_fee_d * Decimal(str(cnt)), currency)
            net_ann_d = max(Decimal("0.00"), ann_gross_d - total_fee_d)
            drag_pct = (
                float(round((total_fee_d / ann_gross_d) * Decimal("100"), 3))
                if ann_gross_d > 0
                else 0.0
            )
            payout_per_batch = (
                float(round_currency(ann_gross_d / Decimal(str(cnt)), currency))
                if cnt > 0
                else 0.0
            )

            results[freq] = {
                "withdrawals_per_year": cnt,
                "annual_withdrawal_fees": float(total_fee_d),
                "net_annual_received": float(net_ann_d),
                "fee_drag_pct": drag_pct,
                "gross_per_withdrawal": payout_per_batch,
            }

        return results

    @classmethod
    def compare_scenarios(
        cls,
        gross_amount: float,
        currency: str,
        scenarios: list[dict[str, Any]],
        target_currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """Compare multiple platform scenarios side by side."""
        comparisons = []
        for s in scenarios:
            name = s.get("name", "Scenario")
            calc = cls.calculate_gross_to_net(
                gross_amount=gross_amount,
                currency=currency,
                target_currency=target_currency or s.get("target_currency"),
                contract_service_fee_pct=s.get("contract_service_fee_pct", 0.0),
                contract_service_fee_fixed=s.get("contract_service_fee_fixed", 0.0),
                fee_tax_pct=s.get("fee_tax_pct", 0.0),
                withholding_tax_pct=s.get("withholding_tax_pct", 0.0),
                withholding_tax_base=s.get("withholding_tax_base", "gross"),
                withdrawal_fee=s.get("withdrawal_fee", 0.0),
                withdrawal_count=s.get("withdrawal_count", 1),
                processor_fee_pct=s.get("processor_fee_pct", 0.0),
                processor_fee_fixed=s.get("processor_fee_fixed", 0.0),
                other_expenses=s.get("other_expenses", 0.0),
                benchmark_fx_rate=s.get("benchmark_fx_rate"),
                actual_fx_rate=s.get("actual_fx_rate"),
            )
            comparisons.append({
                "scenario_name": name,
                "name": name,
                "platform": s.get("platform", "custom"),
                "net_payout": calc.net_payout_amount,
                "bank_deposit": calc.bank_deposit_amount,
                "deposit_currency": calc.target_currency or calc.currency,
                "permanent_cost": calc.permanent_costs,
                "recoverable_credit": calc.recoverable_credits,
                "effective_take_home_pct": calc.effective_take_home_pct,
            })
        return comparisons
