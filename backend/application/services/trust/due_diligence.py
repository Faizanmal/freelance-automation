"""Lead due-diligence checklist — explanations, not verdicts."""

from __future__ import annotations

from typing import Any

from backend.application.services.trust.risk_indicators import RiskIndicator


def build_due_diligence_checklist(
    *,
    indicators: list[RiskIndicator],
    extraction: Any,
    employer_panel: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {
            "id": "verify_source_link",
            "title": "Open the original listing on the source platform",
            "why_it_matters": "Excerpts can omit fees, tests, or contact tricks.",
            "what_to_verify": "URL scheme is https; page matches title/company.",
            "severity": "info",
            "is_verdict": False,
        },
        {
            "id": "clarify_budget_scope",
            "title": "Confirm budget, deliverables, and payment method",
            "why_it_matters": "Unclear scope burns proposal time; missing budget is common, not proof of fraud.",
            "what_to_verify": (
                f"Budget structure: {getattr(extraction, 'budget_structure', None) or 'unknown'}; "
                f"missing fields: {', '.join(getattr(extraction, 'ambiguous_or_missing', [])[:5]) or 'none flagged'}"
            ),
            "severity": "info",
            "is_verdict": False,
        },
        {
            "id": "employer_identity",
            "title": "Check employer identity on a public page",
            "why_it_matters": "Knowing who pays reduces wasted outreach — still not a fraud score.",
            "what_to_verify": (
                (employer_panel or {}).get("company_name")
                or "Employer unknown — ask for a public company or profile link"
            ),
            "severity": "info"
            if (employer_panel or {}).get("company_name")
            else "low",
            "is_verdict": False,
        },
        {
            "id": "no_upfront_payment",
            "title": "Refuse payment-before-work or credential requests",
            "why_it_matters": "Application fees, wires, and seed phrases are classic abuse patterns.",
            "what_to_verify": "You are never asked to pay the client or share bank/wallet secrets.",
            "severity": "high",
            "is_verdict": False,
        },
        {
            "id": "cap_unpaid_tests",
            "title": "Cap unpaid tests to a short paid-or-scoped sample",
            "why_it_matters": "Large unpaid builds transfer risk onto you.",
            "what_to_verify": "Time-box any sample; prefer paid trials.",
            "severity": "medium",
            "is_verdict": False,
        },
    ]

    for ind in indicators:
        if ind.abstain and ind.code == "unknown_employer":
            continue
        items.append(
            {
                "id": f"indicator:{ind.code}",
                "title": ind.label,
                "why_it_matters": ind.why_it_matters,
                "what_to_verify": ind.what_to_verify,
                "severity": ind.severity,
                "observation": ind.observation,
                "is_verdict": False,
            }
        )

    # Deduplicate by id
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        out.append(item)
    return out[:12]
