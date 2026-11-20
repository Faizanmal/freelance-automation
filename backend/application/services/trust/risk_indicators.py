"""Transparent risk indicators — assistance, not a fraud verdict."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal
from urllib.parse import urlparse

Severity = Literal["info", "low", "medium", "high"]

# Never infer from protected traits / nationality / geography alone.
_FORBIDDEN_INFERENCE = re.compile(
    r"(?i)\b(?:nationality|race|ethnicity|religion|gender|sexual\s+orientation|"
    r"disability|age\s+only|from\s+[a-z]{2,}\s+only\s+scam)\b"
)


@dataclass(slots=True)
class RiskIndicator:
    code: str
    label: str
    severity: Severity
    observation: str
    why_it_matters: str
    what_to_verify: str
    excerpt: str | None = None
    confidence: float | None = None
    abstain: bool = False
    # Explicit: never a scam/fraud declaration
    is_verdict: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["disclaimer"] = (
            "Indicator only — not a determination that a person or company is fraudulent."
        )
        return d


_PAYMENT_BEFORE = re.compile(
    r"(?i)\b(?:pay\s+(?:before|upfront|first)|wire\s+(?:transfer|money)|"
    r"send\s+(?:money|payment|gift\s*card)|application\s+fee|"
    r"registration\s+fee|processing\s+fee)\b"
)
_PERSONAL_DATA = re.compile(
    r"(?i)\b(?:ssn|social\s+security|passport\s+scan|copy\s+of\s+(?:id|passport)|"
    r"bank\s+(?:login|password)|seed\s+phrase|private\s+key|"
    r"mother'?s?\s+maiden)\b"
)
_UNPAID_TEST = re.compile(
    r"(?i)\b(?:unpaid\s+test|test\s+project\s+unpaid|work\s+sample\s+unpaid|"
    r"free\s+trial\s+work|do\s+this\s+task\s+for\s+free|"
    r"multi[\s-]?day\s+(?:unpaid\s+)?(?:assignment|test))\b"
)
_SEED_WALLET = re.compile(
    r"(?i)\b(?:seed\s+phrase|wallet\s+seed|send\s+(?:me\s+)?(?:your\s+)?(?:bank|wallet))\b"
)
_URGENT_SPAM = re.compile(r"(?i)\burgent!{2,}|\bguaranteed\s+income\b|\bcrypto\s+airdrop\b")
_EXPOSURE = re.compile(r"(?i)\b(?:for\s+exposure|equity\s+only|unpaid\b)")


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host or None
    except Exception:  # noqa: BLE001
        return None


def assess_risk_indicators(
    *,
    title: str,
    description: str,
    url: str | None = None,
    company: str | None = None,
    source_name: str | None = None,
    enrichment: dict[str, Any] | None = None,
    is_duplicate_suspected: bool = False,
    budget_min: float | None = None,
    budget_max: float | None = None,
) -> list[RiskIndicator]:
    """Pattern-based indicators with explanations. Abstain when evidence is thin."""
    blob = f"{title}\n{description}"
    indicators: list[RiskIndicator] = []

    # Guard: do not emit geography/nationality-based scam claims.
    if _FORBIDDEN_INFERENCE.search(blob):
        # Still scan other patterns; we simply never emit a geo-based indicator.
        pass

    def add(
        code: str,
        label: str,
        severity: Severity,
        observation: str,
        why: str,
        verify: str,
        excerpt: str | None = None,
        confidence: float | None = 0.7,
    ) -> None:
        indicators.append(
            RiskIndicator(
                code=code,
                label=label,
                severity=severity,
                observation=observation,
                why_it_matters=why,
                what_to_verify=verify,
                excerpt=excerpt,
                confidence=confidence,
                is_verdict=False,
            )
        )

    if _PAYMENT_BEFORE.search(blob):
        m = _PAYMENT_BEFORE.search(blob)
        add(
            "payment_before_work",
            "Payment or fee requested before work",
            "high",
            "Listing language suggests payment, wire, gift card, or application fee before delivering work.",
            "Legitimate clients rarely require you to pay them to start.",
            "Confirm fee is not required; use platform escrow; never wire personal funds.",
            excerpt=m.group(0) if m else None,
            confidence=0.8,
        )

    if _PERSONAL_DATA.search(blob) or _SEED_WALLET.search(blob):
        m = _PERSONAL_DATA.search(blob) or _SEED_WALLET.search(blob)
        add(
            "sensitive_personal_data",
            "Unusual personal or financial data request",
            "high",
            "Listing asks for sensitive identity, bank, or wallet credentials.",
            "Early-stage postings should not need passport scans or seed phrases.",
            "Refuse; report on the source platform; do not send secrets.",
            excerpt=m.group(0) if m else None,
            confidence=0.85,
        )

    if _UNPAID_TEST.search(blob):
        m = _UNPAID_TEST.search(blob)
        add(
            "excessive_unpaid_test",
            "Possible unpaid / excessive test work",
            "medium",
            "Mentions unpaid test, free trial work, or multi-day unpaid assignment.",
            "Small paid samples are common; large unpaid builds transfer risk to you.",
            "Ask for a paid trial or scoped sample with a clear time cap.",
            excerpt=m.group(0) if m else None,
            confidence=0.65,
        )

    if _EXPOSURE.search(blob) or _URGENT_SPAM.search(blob):
        m = _EXPOSURE.search(blob) or _URGENT_SPAM.search(blob)
        add(
            "compensation_or_spam_language",
            "Weak compensation or spammy urgency language",
            "medium",
            "Signals like unpaid, equity-only, exposure, guaranteed income, or extreme urgency.",
            "These often correlate with low-quality or abusive postings.",
            "Clarify paid scope and timeline before investing proposal time.",
            excerpt=m.group(0) if m else None,
            confidence=0.6,
        )

    # Domain / link mismatch (listing host vs company-named domain — soft signal)
    listing_host = _domain(url)
    if company and listing_host and "." in listing_host:
        company_token = re.sub(r"[^a-z0-9]", "", company.lower())[:24]
        if (
            len(company_token) >= 4
            and company_token not in listing_host.replace(".", "")
            and source_name
            and source_name not in {"remoteok", "arbeitnow", "himalayas", "jobicy"}
            and "boards." not in listing_host
            and "greenhouse" not in listing_host
            and "lever.co" not in listing_host
        ):
            # Only soft — many boards host third-party jobs; abstain if board-like.
            if not any(
                b in listing_host
                for b in ("upwork", "freelancer", "linkedin", "indeed", "glassdoor")
            ):
                add(
                    "domain_name_mismatch",
                    "Company name and listing domain look unrelated",
                    "low",
                    f"Employer text “{company[:60]}” does not appear in host “{listing_host}”.",
                    "Mismatch can be normal on boards, or a spoofed landing page.",
                    "Open the URL carefully; verify the hiring org on a known public page.",
                    confidence=0.4,
                )

    enrich = enrichment or {}
    flags = [str(f).lower() for f in (enrich.get("quality_flags") or [])]
    if "unpaid" in flags or "exposure" in flags or "spam" in flags:
        add(
            "enrichment_quality_flag",
            "Quality flag from listing analysis",
            "medium",
            f"Enrichment quality_flags include: {', '.join(flags)}",
            "Heuristic flags highlight wording worth a second look.",
            "Read the original listing; do not treat flags as a ban.",
            confidence=0.55,
        )

    if is_duplicate_suspected:
        add(
            "duplicate_or_misleading_repost",
            "Possible duplicate or recycled posting",
            "low",
            "Fingerprint or URL signals suggest this may overlap another listing.",
            "Duplicates waste bid time and can hide stale roles.",
            "Compare titles/URLs; prefer the freshest verified source link.",
            confidence=0.5,
        )

    has_budget = budget_min is not None or budget_max is not None
    if not has_budget and not enrich.get("budget_period"):
        # Unclear scope/budget — info, not scam
        add(
            "unclear_budget",
            "Budget not specified",
            "info",
            "No structured compensation range was found.",
            "Unclear budget makes opportunity cost hard to judge — not proof of fraud.",
            "Ask for rate/budget and payment method before deep proposal work.",
            confidence=0.5,
        )

    # Unknown company → explicit abstention (never mark as scam)
    if not (company and str(company).strip()):
        indicators.append(
            RiskIndicator(
                code="unknown_employer",
                label="Employer not identified",
                severity="info",
                observation="No employer name on the listing.",
                why_it_matters="Missing identity reduces what you can independently verify.",
                what_to_verify="Ask for a public company page or verified profile — do not assume fraud.",
                confidence=None,
                abstain=True,
                is_verdict=False,
            )
        )

    return indicators


def risk_panel_payload(indicators: list[RiskIndicator]) -> dict[str, Any]:
    high = [i for i in indicators if i.severity == "high" and not i.abstain]
    return {
        "indicators": [i.to_dict() for i in indicators],
        "high_count": len(high),
        "requires_human_review": len(high) >= 1,
        "automatic_exclusion": False,
        "verdict": None,
        "disclaimer": (
            "Risk indicators assist due diligence. They are not a determination "
            "that a person or company is fraudulent. Unknown companies are not "
            "marked as scams. High-impact native moderation uses human review."
        ),
    }
