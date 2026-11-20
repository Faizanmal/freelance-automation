"""Evidence registry — verified / observed / reported / unknown semantics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

EvidenceSemantics = Literal["verified", "observed", "reported", "unknown"]
SignalType = Literal[
    "listing_field",
    "url",
    "domain",
    "budget",
    "work_type",
    "risk_pattern",
    "employer_identity",
    "hiring_page",
    "user_report",
    "moderation",
]
Visibility = Literal["public", "operator", "internal"]


@dataclass(slots=True)
class EvidenceRecord:
    id: str
    scope: Literal["opportunity", "company"]
    scope_key: str
    signal_type: SignalType
    factual_observation: str
    semantics: EvidenceSemantics
    source_url: str | None = None
    excerpt: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    confidence: float | None = None
    expires_at: str | None = None
    visibility: Visibility = "public"
    reviewer_status: Literal["none", "pending", "confirmed", "corrected", "rejected"] = (
        "none"
    )
    correction_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _expiry(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def build_evidence_bundle(
    *,
    job_id: int | None,
    source_name: str,
    source_url: str | None,
    company: str | None,
    title: str,
    extraction: Any,
    risk_indicators: list[Any],
    employer_panel: dict[str, Any] | None = None,
) -> list[EvidenceRecord]:
    """Build opportunity/company-scoped evidence with provenance visibility."""
    scope_key = f"job:{job_id}" if job_id is not None else f"url:{source_url or title}"
    company_key = f"company:{(company or 'unknown').strip().lower()[:120]}"
    rows: list[EvidenceRecord] = []

    rows.append(
        EvidenceRecord(
            id=str(uuid4()),
            scope="opportunity",
            scope_key=scope_key,
            signal_type="listing_field",
            factual_observation=f"Title observed: {title[:160]}",
            semantics="observed",
            source_url=source_url,
            excerpt=title[:160],
            confidence=0.95,
            expires_at=_expiry(45),
            visibility="public",
        )
    )
    if source_url:
        rows.append(
            EvidenceRecord(
                id=str(uuid4()),
                scope="opportunity",
                scope_key=scope_key,
                signal_type="url",
                factual_observation=f"Canonical listing URL from {source_name}",
                semantics="observed",
                source_url=source_url,
                confidence=0.9,
                expires_at=_expiry(30),
                visibility="public",
            )
        )
    else:
        rows.append(
            EvidenceRecord(
                id=str(uuid4()),
                scope="opportunity",
                scope_key=scope_key,
                signal_type="url",
                factual_observation="Listing URL unknown",
                semantics="unknown",
                visibility="public",
            )
        )

    if company and company.strip():
        rows.append(
            EvidenceRecord(
                id=str(uuid4()),
                scope="company",
                scope_key=company_key,
                signal_type="employer_identity",
                factual_observation=f"Employer name as stated on listing: {company.strip()[:120]}",
                semantics="observed",
                source_url=source_url,
                confidence=0.6,
                expires_at=_expiry(60),
                visibility="public",
            )
        )
    else:
        rows.append(
            EvidenceRecord(
                id=str(uuid4()),
                scope="company",
                scope_key=company_key,
                signal_type="employer_identity",
                factual_observation="Employer identity not stated",
                semantics="unknown",
                visibility="public",
            )
        )

    # Extraction field pointers → evidence
    for ptr in getattr(extraction, "field_evidence", []) or []:
        status = getattr(ptr, "status", "unknown")
        semantics: EvidenceSemantics = (
            "observed"
            if status == "observed"
            else ("unknown" if status == "unknown" else "observed")
        )
        rows.append(
            EvidenceRecord(
                id=str(uuid4()),
                scope="opportunity",
                scope_key=scope_key,
                signal_type="listing_field",
                factual_observation=f"{ptr.field}={ptr.value!r}"[:240],
                semantics=semantics,
                source_url=source_url,
                excerpt=getattr(ptr, "evidence_excerpt", None),
                confidence=getattr(ptr, "confidence", None),
                expires_at=_expiry(30),
                visibility="public",
            )
        )

    for ind in risk_indicators:
        rows.append(
            EvidenceRecord(
                id=str(uuid4()),
                scope="opportunity",
                scope_key=scope_key,
                signal_type="risk_pattern",
                factual_observation=getattr(ind, "observation", str(ind))[:240],
                semantics="observed",
                source_url=source_url,
                excerpt=getattr(ind, "excerpt", None),
                confidence=getattr(ind, "confidence", None),
                expires_at=_expiry(14),
                visibility="public",
            )
        )

    if employer_panel:
        hiring = employer_panel.get("public_hiring_page")
        if hiring:
            rows.append(
                EvidenceRecord(
                    id=str(uuid4()),
                    scope="company",
                    scope_key=company_key,
                    signal_type="hiring_page",
                    factual_observation="Public hiring page candidate URL",
                    semantics="observed"
                    if employer_panel.get("hiring_page_verified")
                    else "unknown",
                    source_url=str(hiring)[:2048],
                    confidence=0.5 if employer_panel.get("hiring_page_verified") else None,
                    expires_at=_expiry(14),
                    visibility="public",
                )
            )
        domain = employer_panel.get("domain")
        if domain:
            rows.append(
                EvidenceRecord(
                    id=str(uuid4()),
                    scope="company",
                    scope_key=company_key,
                    signal_type="domain",
                    factual_observation=f"Associated domain: {domain}",
                    semantics="observed" if employer_panel.get("domain_from") else "unknown",
                    source_url=source_url,
                    confidence=0.55,
                    expires_at=_expiry(30),
                    visibility="public",
                )
            )

    return rows


def evidence_summary(records: list[EvidenceRecord]) -> dict[str, Any]:
    by_sem: dict[str, int] = {}
    for r in records:
        by_sem[r.semantics] = by_sem.get(r.semantics, 0) + 1
    return {
        "count": len(records),
        "by_semantics": by_sem,
        "note": (
            "No universal reputation score. Trust recency and provenance "
            "are per-evidence; unknown companies are not marked as scams."
        ),
        "records": [r.to_dict() for r in records],
    }
