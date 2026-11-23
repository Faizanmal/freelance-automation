"""Normalize adapter JobCandidate rows into ExternalOpportunity (nulls, not guesses)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.ingestion.contracts import (
    ExternalOpportunity,
    FieldEvidence,
    classify_work_type,
)
from backend.application.services.duplicate_detection import JobCandidate


def safe_http_url(url: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    raw = str(url).strip()
    try:
        parsed = urlparse(raw)
    except Exception:  # noqa: BLE001
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return raw


def candidate_to_opportunity(
    candidate: JobCandidate,
    *,
    ingestion_version: str = "1",
) -> ExternalOpportunity:
    meta = dict(candidate.metadata or {})
    tags = [str(t) for t in (meta.get("tags") or [])]
    work_type, wt_evidence = classify_work_type(
        title=candidate.title or "",
        description=candidate.description or "",
        tags=tags,
        source_hint=candidate.source_name,
    )
    url = safe_http_url(candidate.url) or ""
    evidence = [
        FieldEvidence(field="work_type", value=work_type, source="classifier", note=";".join(wt_evidence)),
    ]
    candidate_bmin = getattr(candidate, "budget_min", None)
    candidate_bmax = getattr(candidate, "budget_max", None)
    if candidate_bmin is not None or candidate_bmax is not None:
        evidence.append(
            FieldEvidence(
                field="compensation",
                value={"min": candidate_bmin, "max": candidate_bmax},
                source=candidate.source_name,
                note="period_unknown_no_fx",
            )
        )
    now = datetime.now(UTC)
    remote = None
    loc = meta.get("location")
    if isinstance(loc, str) and loc:
        remote = "remote" in loc.lower()
    return ExternalOpportunity(
        source_name=candidate.source_name,
        source_id=str(candidate.source_id),
        canonical_url=url,
        title=(candidate.title or "").strip() or "Untitled",
        description=(candidate.description or None) or None,
        summary=None,
        employer=candidate.company,
        work_type=work_type,
        compensation_min=getattr(candidate, "budget_min", None),
        compensation_max=getattr(candidate, "budget_max", None),
        compensation_currency=meta.get("currency") if isinstance(meta.get("currency"), str) else None,
        compensation_period="unknown",
        location=str(loc) if loc else None,
        remote_eligible=remote,
        skills=tags[:40],
        posted_at=getattr(candidate, "posted_at", None),
        first_seen_at=now,
        last_seen_at=now,
        last_checked_at=now,
        expires_at=None,
        state="active" if url else "unknown",
        provenance={
            "adapter": candidate.source_name,
            "ingestion_version": ingestion_version,
        },
        evidence=evidence,
        ingestion_version=ingestion_version,
        metadata=meta,
    )


def opportunity_to_candidate(opp: ExternalOpportunity) -> JobCandidate:
    """Bridge back to existing JobIngestionService path."""
    meta = dict(opp.metadata)
    meta["work_type"] = opp.work_type
    meta["compensation_period"] = opp.compensation_period
    meta["compensation_currency"] = opp.compensation_currency
    meta["remote_eligible"] = opp.remote_eligible
    meta["location"] = opp.location or meta.get("location")
    meta["tags"] = opp.skills or meta.get("tags") or []
    meta["provenance"] = opp.provenance
    meta["classification_evidence"] = [
        {"field": e.field, "value": e.value, "source": e.source, "note": e.note}
        for e in opp.evidence
    ]
    return JobCandidate(
        source_name=opp.source_name,
        source_id=opp.source_id,
        title=opp.title,
        description=opp.description or "",
        url=opp.canonical_url,
        company=opp.employer,
        budget_min=opp.compensation_min,
        budget_max=opp.compensation_max,
        posted_at=opp.posted_at,
        metadata=meta,
    )


def fingerprint_opportunity(opp: ExternalOpportunity) -> str:
    """Normalized fingerprint for conservative dedup (not semantic merge)."""
    import hashlib
    import re

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").lower().strip())

    host = ""
    try:
        host = urlparse(opp.canonical_url).netloc.lower()
    except Exception:  # noqa: BLE001
        host = ""
    raw = "|".join(
        [
            opp.source_name,
            opp.source_id,
            host,
            norm(opp.title),
            norm(opp.employer or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def enrich_candidate_classification(candidate: JobCandidate) -> JobCandidate:
    """Attach work_type evidence onto candidate.metadata in place."""
    opp = candidate_to_opportunity(candidate)
    return opportunity_to_candidate(opp)


def inventory_quality_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute simple quality metrics over opportunity-like dicts."""
    n = len(rows)
    if n == 0:
        return {
            "count": 0,
            "with_url": 0,
            "with_employer": 0,
            "work_type_known_rate": 0.0,
            "stale_marked_rate": 0.0,
        }
    with_url = sum(1 for r in rows if r.get("url") or r.get("canonical_url"))
    with_employer = sum(1 for r in rows if r.get("company") or r.get("employer"))
    known_wt = sum(
        1
        for r in rows
        if (r.get("work_type") or (r.get("metadata") or {}).get("work_type") or "unknown")
        != "unknown"
    )
    stale = sum(
        1
        for r in rows
        if r.get("is_expired") or r.get("state") in {"expired", "removed"}
    )
    return {
        "count": n,
        "with_url": with_url,
        "with_employer": with_employer,
        "work_type_known_rate": round(known_wt / n, 4),
        "stale_marked_rate": round(stale / n, 4),
        "url_coverage": round(with_url / n, 4),
    }
