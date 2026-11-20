"""Canonical discovery contracts — separate from user ranking/digest."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

WorkType = Literal["freelance", "contract", "full_time", "unknown"]
CompensationPeriod = Literal["hour", "day", "week", "month", "year", "fixed", "unknown"]
OpportunityState = Literal[
    "active", "duplicate", "expired", "removed", "unknown", "quarantined"
]


@dataclass(slots=True)
class FieldEvidence:
    """Field-level provenance without inventing values."""

    field: str
    value: Any
    source: str
    confidence: float | None = None
    note: str | None = None


@dataclass(slots=True)
class ExternalOpportunity:
    """
    Canonical external opportunity (shared inventory).

    Nulls are preferred over fabrications. Ranking/digest stay outside this schema.
    """

    source_name: str
    source_id: str
    canonical_url: str
    title: str
    description: str | None = None
    summary: str | None = None
    employer: str | None = None
    work_type: WorkType = "unknown"
    compensation_min: float | None = None
    compensation_max: float | None = None
    compensation_currency: str | None = None
    compensation_period: CompensationPeriod = "unknown"
    location: str | None = None
    remote_eligible: bool | None = None
    skills: list[str] = field(default_factory=list)
    posted_at: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_checked_at: datetime | None = None
    expires_at: datetime | None = None
    state: OpportunityState = "active"
    provenance: dict[str, Any] = field(default_factory=dict)
    evidence: list[FieldEvidence] = field(default_factory=list)
    ingestion_version: str = "1"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def external_key(self) -> str:
        return f"{self.source_name}:{self.source_id}"


class SourceAdapter(Protocol):
    """Minimal adapter surface used by the governance gate + scrape runner."""

    name: str

    async def fetch(
        self, *, limit: int = 50, **kwargs: Any
    ) -> list[Any]:  # JobCandidate or ExternalOpportunity
        ...

    async def health_check(self) -> dict[str, Any]:
        ...


def classify_work_type(
    *,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    source_hint: str | None = None,
) -> tuple[WorkType, list[str]]:
    """Heuristic classification with evidence strings — never invents pay."""
    blob = f"{title} {description} {' '.join(tags or [])}".lower()
    evidence: list[str] = []
    if source_hint in {"serpapi_freelance", "reddit_hiring", "hn_hiring"}:
        evidence.append(f"source_hint:{source_hint}")
    if any(
        t in blob
        for t in (
            "freelance",
            "freelancer",
            "gig",
            "independent contractor",
            "1099",
        )
    ):
        evidence.append("keyword:freelance")
        return "freelance", evidence
    if any(
        t in blob
        for t in ("contract", "contractor", "fixed-term", "temp-to-hire", "c2c")
    ):
        evidence.append("keyword:contract")
        return "contract", evidence
    if any(
        t in blob
        for t in (
            "full-time",
            "full time",
            "permanent",
            "w2",
            "salary",
            "benefits package",
        )
    ):
        evidence.append("keyword:full_time")
        return "full_time", evidence
    if source_hint in {"serpapi_freelance", "reddit_hiring"}:
        return "freelance", evidence or ["source_default:freelance"]
    return "unknown", evidence or ["insufficient_signal"]
