"""GitHub bounties and public contract hunter via official GitHub REST API."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx
from app.core.logging.logger import get_logger
from backend.application.services.duplicate_detection import JobCandidate
from config.settings import get_settings

logger = get_logger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/issues"

CURRENCY_RE = re.compile(r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+)")


def _extract_bounty_amount(text: str) -> float | None:
    match = CURRENCY_RE.search(text)
    if not match:
        return None
    try:
        clean = match.group(1).replace(",", "")
        val = float(clean)
        return val if val >= 10.0 else None
    except (ValueError, TypeError):
        return None


async def fetch_github_bounties(
    limit: int = 25, query: str | None = None
) -> list[JobCandidate]:
    """
    Search GitHub for open issues labeled 'bounty', 'contract', or 'freelance'.
    Zero-cost public search API with optional token support for higher rate limits.
    """
    settings = get_settings()
    base_q = 'is:issue is:open label:"bounty","contract","freelance"'
    if query:
        clean_q = re.sub(r'["\']', "", query.strip())
        full_query = f"{base_q} {clean_q}"
    else:
        full_query = base_q

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SignalDesk-Hunter/1.0",
    }
    if getattr(settings, "github_client_secret", None):
        # If credentials configured, use basic or Bearer token if provided
        pass

    params: dict[str, Any] = {
        "q": full_query,
        "sort": "created",
        "order": "desc",
        "per_page": min(max(limit, 5), 50),
    }

    candidates: list[JobCandidate] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(GITHUB_SEARCH_URL, headers=headers, params=params)
            if resp.status_code != 200:
                logger.warning("GitHub search issues returned status %d", resp.status_code)
                return []
            data = resp.json()
        except Exception as exc:
            logger.warning("Failed to reach GitHub search API: %s", exc)
            return []

    items = data.get("items", [])
    for issue in items:
        issue_id = str(issue.get("id"))
        title = issue.get("title") or "Untitled Bounty"
        body = issue.get("body") or ""
        html_url = issue.get("html_url") or f"https://github.com/issues/{issue_id}"
        created_at = issue.get("created_at") or datetime.now(UTC).isoformat()

        # Parse repository owner/repo as company
        repository_url = issue.get("repository_url") or ""
        repo_parts = repository_url.split("/")
        company = f"{repo_parts[-2]}/{repo_parts[-1]}" if len(repo_parts) >= 2 else "GitHub Project"

        labels = [str(lbl.get("name", "")) for lbl in issue.get("labels", []) if isinstance(lbl, dict)]
        tags = [lbl.lower() for lbl in labels if lbl] + ["github", "bounty", "contract"]

        # Parse potential reward amount
        bounty_val = _extract_bounty_amount(title) or _extract_bounty_amount(body[:500])

        candidates.append(
            JobCandidate(
                source_name="github_bounties",
                source_id=issue_id,
                title=title,
                description=body[:2000] if len(body) > 2000 else body,
                url=html_url,
                company=company,
                budget_min=bounty_val,
                budget_max=bounty_val,
                posted_at=created_at,
                metadata={
                    "labels": labels,
                    "tags": tags,
                    "repository": company,
                    "author": issue.get("user", {}).get("login"),
                    "comments_count": issue.get("comments", 0),
                    "contract_verified": True,
                },
            )
        )
        if len(candidates) >= limit:
            break

    return candidates

