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


_SINGLE_POSTING_PATH_RE = re.compile(
    r"/(?:jobs?|openings?|positions?|j|role|posting)/[a-z0-9_-]{6,}",
    re.IGNORECASE,
)


def diversify(
    ranked: list[RankedMatch],
    *,
    max_per_source: int = 4,
    max_per_company: int = 3,
    max_per_domain: int = 1,
) -> list[RankedMatch]:
    """Soft diversity: prefer variety while preserving relative order.

    Hard-caps one result per domain (no exceptions) so boards like 9am.works
    never appear twice in the top leads.
    """
    source_counts: dict[str, int] = defaultdict(int)
    company_counts: dict[str, int] = defaultdict(int)
    domain_seen: set[str] = set()
    primary: list[RankedMatch] = []
    deferred: list[RankedMatch] = []

    for item in ranked:
        source = (item.job.source_name or "unknown").lower()
        company = (item.job.company or "").strip().lower() or "unknown"
        domain = _domain_key(item.job.url)
        # Hard-cap domains for both primary and deferred — never allow a second
        # listing from the same host even when source/company soft-caps defer.
        if max_per_domain > 0 and domain and domain != "unknown" and domain in domain_seen:
            continue
        if (
            source_counts[source] >= max_per_source
            or company_counts[company] >= max_per_company
        ):
            if domain and domain != "unknown":
                domain_seen.add(domain)
            deferred.append(item)
            continue
        source_counts[source] += 1
        company_counts[company] += 1
        if domain and domain != "unknown":
            domain_seen.add(domain)
        primary.append(item)

    return primary + deferred


def _domain_key(url: str | None) -> str:
    raw = (url or "").strip().lower()
    if not raw:
        return "unknown"
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or "").lower().removeprefix("www.")
        return host or "unknown"
    except Exception:
        return "unknown"


def _is_distinct_single_posting(item: RankedMatch) -> bool:
    url = (item.job.url or "").strip()
    if not url:
        return False
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        path = parsed.path or ""
    except Exception:
        return False
    return bool(_SINGLE_POSTING_PATH_RE.search(path))

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
