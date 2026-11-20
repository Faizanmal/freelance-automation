"""Employer research panel — permitted public signals only."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from backend.application.services.trust.safe_fetch import (
    DEFAULT_ALLOWLIST_SUFFIXES,
    host_allowed,
    safe_fetch_text,
    validate_public_url,
)


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:  # noqa: BLE001
        return None


def build_employer_panel(
    *,
    company: str | None,
    listing_url: str | None,
    source_name: str | None = None,
    posted_at: str | None = None,
    first_seen_at: str | None = None,
    enrichment: dict[str, Any] | None = None,
    fetched: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Assemble employer identity / public hiring context without private contacts
    or mass personal enrichment.
    """
    domain = _domain_from_url(listing_url)
    domain_from = "listing_url" if domain else None
    hiring_page = None
    hiring_verified = False
    if listing_url and domain and host_allowed(domain):
        hiring_page = listing_url
        hiring_verified = True  # URL itself is the observed hiring/apply page

    enrich = enrichment or {}
    project_context = None
    if enrich.get("summary"):
        project_context = str(enrich["summary"])[:400]
    elif enrich.get("project_type"):
        project_context = str(enrich["project_type"])[:120]

    panel = {
        "company_name": (company.strip() if company else None) or None,
        "company_identity_status": (
            "observed" if company and str(company).strip() else "unknown"
        ),
        "domain": domain,
        "domain_from": domain_from,
        "public_hiring_page": hiring_page,
        "hiring_page_verified": hiring_verified,
        "source_name": source_name,
        "project_context": project_context,
        "timestamps": {
            "posted_at": posted_at,
            "first_seen_at": first_seen_at,
            "researched_at": datetime.now(UTC).isoformat(),
        },
        "private_contacts": None,  # never populated
        "mass_enrichment": False,
        "fetched_page": None,
        "notes": [
            "Panel uses listing provenance and allowlisted public hosts only.",
            "Unknown companies are not labeled as scams.",
            "Do not treat this as a background check.",
        ],
        "disclaimer": (
            "Employer research is limited to permitted public signals. "
            "No private contact scraping."
        ),
    }
    if fetched:
        panel["fetched_page"] = {
            "ok": fetched.get("ok"),
            "final_url": fetched.get("final_url"),
            "status_code": fetched.get("status_code"),
            "text_excerpt": fetched.get("text_excerpt"),
            "blocked_reason": fetched.get("blocked_reason"),
            "error": fetched.get("error"),
        }
        if fetched.get("ok") and fetched.get("final_url"):
            panel["public_hiring_page"] = fetched["final_url"]
            panel["hiring_page_verified"] = True
    return panel


async def research_employer_with_fetch(
    *,
    company: str | None,
    listing_url: str | None,
    source_name: str | None = None,
    posted_at: str | None = None,
    first_seen_at: str | None = None,
    enrichment: dict[str, Any] | None = None,
    fetch: bool = False,
) -> dict[str, Any]:
    fetched = None
    if fetch and listing_url:
        ok, reason = validate_public_url(
            listing_url, allow_suffixes=DEFAULT_ALLOWLIST_SUFFIXES
        )
        if ok:
            result = await safe_fetch_text(listing_url)
            fetched = result.to_dict()
        else:
            fetched = {
                "ok": False,
                "url": listing_url,
                "blocked_reason": reason,
                "text_excerpt": None,
            }
    return build_employer_panel(
        company=company,
        listing_url=listing_url,
        source_name=source_name,
        posted_at=posted_at,
        first_seen_at=first_seen_at,
        enrichment=enrichment,
        fetched=fetched,
    )
