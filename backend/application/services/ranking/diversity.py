"""Post-rank diversity across sources/employers and duplicate collapse."""

from __future__ import annotations

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


def _dedupe_key(item: RankedMatch) -> str:
    job = item.job
    canonical = (getattr(job, "canonical_id", None) or "").strip().lower()
    if canonical:
        return f"canonical:{canonical}"
    url = (job.url or "").strip().lower()
    if url:
        parsed = urlparse(url)
        host_path = f"{parsed.netloc}{parsed.path}".rstrip("/")
        if host_path:
            return f"url:{host_path}"
    title = (job.title or "").strip().lower()
    company = (job.company or "").strip().lower()
    return f"title:{title}|company:{company}"
