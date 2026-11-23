"""Post-rank diversity across sources/employers and duplicate collapse."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from backend.application.services.ranking.pipeline import RankedMatch


def collapse_duplicates(ranked: list[RankedMatch]) -> list[RankedMatch]:
    """Keep highest-scoring item per canonical/url/title+company key."""
    seen: set[str] = set()
    out: list[RankedMatch] = []
    for item in ranked:
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def diversify(
    ranked: list[RankedMatch],
    *,
    max_per_source: int = 4,
    max_per_company: int = 3,
) -> list[RankedMatch]:
    """Soft diversity: prefer variety while preserving relative order."""
    source_counts: dict[str, int] = defaultdict(int)
    company_counts: dict[str, int] = defaultdict(int)
    primary: list[RankedMatch] = []
    deferred: list[RankedMatch] = []

    for item in ranked:
        source = (item.job.source_name or "unknown").lower()
        company = (item.job.company or "").strip().lower() or "unknown"
        if (
            source_counts[source] >= max_per_source
            or company_counts[company] >= max_per_company
        ):
            deferred.append(item)
            continue
        source_counts[source] += 1
        company_counts[company] += 1
        primary.append(item)

    return primary + deferred


def _normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", (title or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Drop common source prefixes that differ across discovery modes.
    for prefix in ("hiring:", "job:", "role:", "position:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned


def _dedupe_key(item: RankedMatch) -> str:
    job = item.job
    # Prefer stable content identity over per-ingest canonical UUIDs so the same
    # role from "Company careers" and "Jobs discovery" collapses together.
    title = _normalize_title(job.title or "")
    company = (job.company or "").strip().lower()
    if title and company and company not in {"unknown", "n/a", "na"}:
        return f"title:{title}|company:{company}"
    url = (job.url or "").strip().lower()
    if url:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().removeprefix("www.")
        path = (parsed.path or "").rstrip("/")
        # Ignore tracking querystrings; keep host+path.
        host_path = f"{host}{path}"
        if host_path:
            return f"url:{host_path}"
    canonical = (getattr(job, "canonical_id", None) or "").strip().lower()
    if canonical:
        return f"canonical:{canonical}"
    return f"title:{title}|company:{company}"
