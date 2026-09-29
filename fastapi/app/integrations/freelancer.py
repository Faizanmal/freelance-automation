from __future__ import annotations

from typing import Any

import httpx

from app.core.logging.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

API_BASE = "https://www.freelancer.com/api"


class SourceNotConfiguredError(RuntimeError):
    """Raised when Freelancer credentials are missing."""


def freelancer_configured() -> bool:
    return bool(get_settings().freelancer_oauth_token)


async def search_projects(*, query: str = "python", limit: int = 20) -> list[dict[str, Any]]:
    settings = get_settings()
    token = settings.freelancer_oauth_token
    if not token:
        raise SourceNotConfiguredError(
            "Freelancer is not configured. Set FREELANCER_OAUTH_TOKEN in the environment."
        )

    headers = {
        "Freelancer-OAuth-V1": token,
        "User-Agent": "FreelanceIntelligence/0.3",
        "Accept": "application/json",
    }
    params: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "offset": 0,
        "full_description": "true",
        "job_details": "true",
    }

    async with httpx.AsyncClient(timeout=45.0, headers=headers, follow_redirects=True) as client:
        response = await client.get(f"{API_BASE}/projects/0.1/projects/active/", params=params)
        if response.status_code in {401, 403}:
            raise SourceNotConfiguredError("Freelancer token rejected (401/403)")
        response.raise_for_status()
        payload = response.json()

    result = payload.get("result") or {}
    projects = result.get("projects") or []
    rows: list[dict[str, Any]] = []
    for project in projects:
        project_id = project.get("id")
        title = project.get("title") or "Untitled"
        description = project.get("description") or title
        seo_url = project.get("seo_url")
        url = f"https://www.freelancer.com/projects/{seo_url}" if seo_url else f"https://www.freelancer.com/projects/{project_id}"
        budget = project.get("budget") or {}
        tags = []
        for job in project.get("jobs") or []:
            name = job.get("name") if isinstance(job, dict) else None
            if name:
                tags.append(str(name).lower())

        rows.append(
            {
                "source_id": str(project_id),
                "title": str(title),
                "description": str(description),
                "url": url,
                "company": "Freelancer.com client",
                "budget_min": _to_float(budget.get("minimum")),
                "budget_max": _to_float(budget.get("maximum")),
                "posted_at": _epoch_to_iso(project.get("time_submitted")),
                "tags": tags,
                "location": "Remote",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = settings.freelancer_oauth_token
    if not token:
        raise SourceNotConfiguredError(
            "Freelancer is not configured. Set FREELANCER_OAUTH_TOKEN in the environment."
        )
    return {
        "Freelancer-OAuth-V1": token,
        "User-Agent": "FreelanceIntelligence/0.4",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def get_self_user_id() -> int:
    async with httpx.AsyncClient(timeout=30.0, headers=_auth_headers(), follow_redirects=True) as client:
        response = await client.get(f"{API_BASE}/users/0.1/self/")
        if response.status_code in {401, 403}:
            raise SourceNotConfiguredError("Freelancer token rejected (401/403)")
        response.raise_for_status()
        payload = response.json()
    result = payload.get("result") or {}
    user = result.get("id") or (result.get("user") or {}).get("id")
    if user is None:
        raise SourceNotConfiguredError("Could not resolve Freelancer self user id")
    return int(user)


async def place_bid(
    *,
    project_id: int,
    amount: float,
    period: int,
    description: str,
    milestone_percentage: int = 100,
    bidder_id: int | None = None,
) -> dict[str, Any]:
    """Place a bid via POST /projects/0.1/bids/."""
    bidder = bidder_id if bidder_id is not None else await get_self_user_id()
    body = {
        "project_id": int(project_id),
        "bidder_id": int(bidder),
        "amount": float(amount),
        "period": int(period),
        "milestone_percentage": int(milestone_percentage),
        "description": description,
    }
    async with httpx.AsyncClient(timeout=45.0, headers=_auth_headers(), follow_redirects=True) as client:
        response = await client.post(f"{API_BASE}/projects/0.1/bids/", json=body)
        if response.status_code in {401, 403}:
            raise SourceNotConfiguredError(
                "Freelancer token rejected for bidding (401/403). "
                "Ensure the token has project bid scopes."
            )
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json()
            except Exception:
                logger.debug("Failed to parse freelancer error response as JSON", exc_info=True)
            raise RuntimeError(f"Freelancer bid failed ({response.status_code}): {detail}")
        payload = response.json()
    result = payload.get("result")
    return result if isinstance(result, dict) else {"raw": payload}


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _epoch_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return str(value) if value else None
