from __future__ import annotations

from typing import Any

from app.ingestion.sources import SOURCE_ATTRIBUTION

EXCERPT_CHARS = 480


def strip_html(value: str) -> str:
    import re

    return re.sub(r"<[^>]+>", " ", value or "")


def make_excerpt(description: str, *, limit: int = EXCERPT_CHARS) -> str:
    clean = " ".join(strip_html(description).split())
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
