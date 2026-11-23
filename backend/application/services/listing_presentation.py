from __future__ import annotations

import re
from typing import Any

from app.ingestion.sources import SOURCE_ATTRIBUTION

EXCERPT_CHARS = 480


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")


def strip_markdown_noise(value: str) -> str:
    """Remove markdown headings and common scraper prefixes from public snippets."""
    if not value:
        return ""
    text = value.replace("\r\n", "\n")
    # Drop ATX headings and Setext-style remnants.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s{0,3}([-=]){3,}\s*$", "", text)
    # Drop "Title: ..." lead-ins that Serp/ATS scrapers leave in.
    text = re.sub(r"(?im)^\s*title\s*:\s*", "", text)
    text = re.sub(r"(?i)\btitle\s*:\s*", "", text, count=1)
    # Inline heading markers that survived as "### Foo".
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_~`]{1,3}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def make_excerpt(description: str, *, limit: int = EXCERPT_CHARS) -> str:
    clean = strip_markdown_noise(strip_html(description))
    clean = " ".join(clean.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def public_job_payload(
    job_dict: dict[str, Any], *, full_description: bool = False
) -> dict[str, Any]:
    """Return a commercial-safe listing: excerpt + attribution + source link."""
    source = str(job_dict.get("source_name") or "")
    description = str(job_dict.get("description") or "")
    attribution = SOURCE_ATTRIBUTION.get(source, source.title() or "Source")
    payload = dict(job_dict)
    if not full_description:
        payload["description"] = make_excerpt(description)
        payload["description_excerpt"] = payload["description"]
        payload["full_description_available"] = False
    else:
        payload["description_excerpt"] = make_excerpt(description)
        payload["full_description_available"] = True
    payload["source_attribution"] = attribution
    payload["source_label"] = f"Listed on {attribution}"
    apply_url = job_dict.get("url")
    # Block non-http(s) schemes from reaching the client.
    if isinstance(apply_url, str):
        lowered = apply_url.strip().lower()
        if not (
            lowered.startswith("http://") or lowered.startswith("https://")
        ):
            apply_url = None
    payload["apply_url"] = apply_url
    # Freshness for UI (users see source + when last verified).
    payload.setdefault("work_type", job_dict.get("work_type") or "unknown")
    payload.setdefault("last_checked_at", job_dict.get("last_checked_at"))
    payload.setdefault("inventory_state", job_dict.get("inventory_state") or "active")
    if payload.get("is_expired"):
        payload["inventory_state"] = payload.get("expired_reason") or "expired"
    return payload
