"""Budget / rate extraction and period normalization.

Hunters store very different numbers in the same ``budget_min`` / ``budget_max``
columns: hourly rates (``$75``), fixed project budgets (``$3,000``) and annual
salaries (``$130,000``). Comparing them raw against one preference silently
drops good leads, so this module labels every budget with a period and
offers period-aware filtering and formatting.

All functions are pure (no I/O, no ORM imports) so matching, enrichment,
lead findings and proposal drafting can share one implementation.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

BudgetPeriod = Literal[
    "hourly", "daily", "weekly", "monthly", "annual", "fixed", "unknown"
]

# Periods that describe a recurring rate (convertible to an hourly equivalent).
RATE_PERIODS: frozenset[str] = frozenset(
    {"hourly", "daily", "weekly", "monthly", "annual"}
)
VALID_PERIODS: frozenset[str] = RATE_PERIODS | {"fixed", "unknown"}

# Standard full-time working hours per period, used for hourly equivalents.
_HOURS_PER_PERIOD: dict[str, float] = {
    "hourly": 1.0,
    "daily": 8.0,
    "weekly": 40.0,
    "monthly": 160.0,
    "annual": 2080.0,
}

_PERIOD_SUFFIX: dict[str, str] = {
    "hourly": "/hr",
    "daily": "/day",
    "weekly": "/wk",
    "monthly": "/mo",
    "annual": "/yr",
}

_PERIOD_ALIASES: dict[str, BudgetPeriod] = {
    "h": "hourly",
    "hr": "hourly",
    "hour": "hourly",
    "hourly": "hourly",
    "per_hour": "hourly",
    "day": "daily",
    "daily": "daily",
    "wk": "weekly",
    "week": "weekly",
    "weekly": "weekly",
    "mo": "monthly",
    "month": "monthly",
    "monthly": "monthly",
    "yr": "annual",
    "year": "annual",
    "yearly": "annual",
    "annum": "annual",
    "annual": "annual",
    "annually": "annual",
    "salary": "annual",
    "fixed": "fixed",
    "fixed_price": "fixed",
    "project": "fixed",
    "one_time": "fixed",
}

_CURRENCY_CODES: dict[str, str] = {
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
}
_CURRENCY_SYMBOLS: dict[str, str] = {"USD": "$", "EUR": "€", "GBP": "£"}

# Magnitude heuristics used only when no explicit unit/context is present.
_HOURLY_CEILING = 300.0  # unlabeled amounts at or below this read as hourly
_ANNUAL_FLOOR = 20_000.0  # unlabeled amounts at or above this read as salary
_HOURLY_CONTEXT_MAX = 1_000.0  # "hourly" wording only trusted below this
_ANNUAL_CONTEXT_MIN = 10_000.0  # "salary" wording only trusted above this
_MIN_PLAUSIBLE = 1.0
_MAX_PLAUSIBLE = 10_000_000.0
_SCAN_LIMIT = 8_000  # characters of description scanned for amounts

_CUR = r"(?:[$€£]|(?<![a-z])(?:usd|eur|gbp))"
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_AMOUNT_RE = re.compile(
    rf"(?P<cur>{_CUR})\s?(?P<lo>{_NUM})\s?(?P<lok>k\b)?"
    rf"(?:\s?(?:-|–|—|to)\s?{_CUR}?\s?(?P<hi>{_NUM})\s?(?P<hik>k\b)?)?"
    rf"(?:\s?(?:/|per|an|a)\s?"
    rf"(?P<unit>hour|hr|h|day|week|wk|month|mo|year|yr|annum)\b"
    rf"|\s(?P<adverb>hourly|daily|weekly|monthly|yearly|annually)\b)?",
    re.IGNORECASE,
)
_HOURLY_CONTEXT = re.compile(r"\bhourly\b|\bper\s+hour\b|/\s?hr\b", re.IGNORECASE)
_ANNUAL_CONTEXT = re.compile(
    r"\bsalary\b|\bper\s+(?:year|annum)\b|\bannual(?:ly)?\b|\bbase\s+pay\b",
    re.IGNORECASE,
)
_FIXED_CONTEXT = re.compile(
    r"\bfixed[\s-]?(?:price|budget|fee)\b|\bflat\s+fee\b|\bone[\s-]?time\b"
    r"|\bproject\s+budget\b|\bbudget\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class BudgetSignal:
    """A budget with its period label. ``minimum``/``maximum`` may be equal."""

    minimum: float | None
    maximum: float | None
    period: BudgetPeriod
    currency: str | None = None

    @property
    def top(self) -> float | None:
        return self.maximum if self.maximum is not None else self.minimum


def normalize_period(raw: Any) -> BudgetPeriod:
    """Map free-form period labels ("yearly", "per hour", "hr") to a period."""
    if raw is None:
        return "unknown"
    key = re.sub(r"[\s\-]+", "_", str(raw).strip().lower())
    return _PERIOD_ALIASES.get(key, "unknown")


def infer_period(amount: float | None, context: str = "") -> BudgetPeriod:
    """Infer a period from surrounding wording, then from magnitude."""
    if amount is not None:
        if amount <= _HOURLY_CONTEXT_MAX and _HOURLY_CONTEXT.search(context):
            return "hourly"
        if amount >= _ANNUAL_CONTEXT_MIN and _ANNUAL_CONTEXT.search(context):
            return "annual"
    if _FIXED_CONTEXT.search(context):
        return "fixed"
    if amount is None:
        return "unknown"
    if amount <= _HOURLY_CEILING:
        return "hourly"
    if amount >= _ANNUAL_FLOOR:
        return "annual"
    return "fixed"


def extract_budget(text: str | None) -> BudgetSignal | None:
    """Find the most explicit currency amount (or range) mentioned in text.

    Requires a currency marker so "5 years" or "10 developers" never match.
    An amount with an explicit unit ("$80/hr") wins over unlabeled ones.
    """
    if not text:
        return None
    sample = text[:_SCAN_LIMIT]
    first: tuple[float, float | None, BudgetPeriod, str] | None = None
    for match in _AMOUNT_RE.finditer(sample):
        parsed = _parse_match(match)
        if parsed is None:
            continue
        if parsed[2] != "unknown":
            first = parsed
            break
        if first is None:
            first = parsed
    if first is None:
        return None
    low, high, period, currency = first
    top = high if high is not None else low
    if period == "unknown":
        period = infer_period(top, sample)
    return BudgetSignal(
        minimum=low,
        maximum=high if high is not None else low,
        period=period,
        currency=currency,
    )


def resolve_budget(
    *,
    budget_min: float | None,
    budget_max: float | None,
    text: str | None,
    period_hint: Any = None,
) -> BudgetSignal | None:
    """Label structured source amounts, or fall back to amounts in the text."""
    if budget_min is None and budget_max is None:
        return extract_budget(text)
    period = normalize_period(period_hint)
    if period == "unknown":
        top = budget_max if budget_max is not None else budget_min
        period = infer_period(top, (text or "")[:_SCAN_LIMIT])
    return BudgetSignal(minimum=budget_min, maximum=budget_max, period=period)


def stored_period(
    enrichment: Mapping[str, Any] | None,
    budget_min: float | None,
    budget_max: float | None,
) -> BudgetPeriod:
    """Period for a persisted job: enrichment label first, magnitude fallback.

    Legacy rows ingested before period labelling have no ``budget_period``;
    magnitude inference keeps them from being compared as project budgets.
    """
    label = str((enrichment or {}).get("budget_period") or "").lower()
    if label in VALID_PERIODS and label != "unknown":
        return label  # type: ignore[return-value]
    top = budget_max if budget_max is not None else budget_min
    return infer_period(top)


def hourly_equivalent(amount: float | None, period: str) -> float | None:
    """Convert a rate to an hourly figure; ``None`` for fixed/unknown."""
    hours = _HOURS_PER_PERIOD.get(period)
    if amount is None or hours is None:
        return None
    return amount / hours


def passes_budget_filter(
    *,
    budget_min: float | None,
    budget_max: float | None,
    period: str,
    min_project_budget: float | None,
    max_project_budget: float | None,
    min_hourly_rate: float | None,
) -> bool:
    """Compare a job budget only against the preference of the same kind.

    Rates (hourly/daily/…/annual) are checked against ``min_hourly_rate``;
    fixed or unlabeled budgets keep the original project-budget rules.
    """
    if period in RATE_PERIODS:
        top = budget_max if budget_max is not None else budget_min
        rate = hourly_equivalent(top, period)
        return min_hourly_rate is None or rate is None or rate >= min_hourly_rate
    if (
        min_project_budget is not None
        and budget_max is not None
        and budget_max < min_project_budget
    ):
        return False
    if (
        max_project_budget is not None
        and budget_min is not None
        and budget_min > max_project_budget
    ):
        return False
    return True


def format_budget(
    budget_min: float | None,
    budget_max: float | None,
    period: str,
    currency: str | None = None,
) -> str | None:
    """Human label such as ``$60–$80/hr``, ``up to $5,000`` or ``$120,000/yr``."""
    low = budget_min if budget_min else None
    high = budget_max if budget_max else None
    if low is None and high is None:
        return None
    code = (currency or "USD").upper()
    symbol = _CURRENCY_SYMBOLS.get(code)
    suffix = _PERIOD_SUFFIX.get(period, "")

    def _fmt(value: float) -> str:
        number = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
        return f"{symbol}{number}" if symbol else f"{number} {code}"

    if low is not None and high is not None:
        if low == high:
            return f"{_fmt(high)}{suffix}"
        return f"{_fmt(low)}–{_fmt(high)}{suffix}"
    if high is not None:
        return f"up to {_fmt(high)}{suffix}"
    return f"from {_fmt(low)}{suffix}"  # type: ignore[arg-type]


def describe_budget(
    budget_min: float | None,
    budget_max: float | None,
    enrichment: Mapping[str, Any] | None,
) -> str | None:
    """Format a persisted job's budget using its stored period and currency."""
    period = stored_period(enrichment, budget_min, budget_max)
    currency = (enrichment or {}).get("budget_currency")
    return format_budget(budget_min, budget_max, period, currency)


def _parse_match(
    match: re.Match[str],
) -> tuple[float, float | None, BudgetPeriod, str] | None:
    low = _parse_number(match.group("lo"), bool(match.group("lok")))
    high_raw = match.group("hi")
    high = _parse_number(high_raw, bool(match.group("hik"))) if high_raw else None
    if low is None:
        return None
    # "$5-8k" means 5,000–8,000: the "k" applies to both ends.
    if high is not None and match.group("hik") and not match.group("lok") and low < 1000:
        low *= 1000
    if high is not None and high < low:
        low, high = high, low
    if not _plausible(low) or (high is not None and not _plausible(high)):
        return None
    unit = match.group("unit") or match.group("adverb")
    period = normalize_period(unit) if unit else "unknown"
    currency = _CURRENCY_CODES.get(match.group("cur").lower(), "USD")
    return low, high, period, currency


def _parse_number(raw: str | None, thousands: bool) -> float | None:
    if not raw:
        return None
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    return value * 1000 if thousands else value


def _plausible(value: float) -> bool:
    return _MIN_PLAUSIBLE <= value <= _MAX_PLAUSIBLE

