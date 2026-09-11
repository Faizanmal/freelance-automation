from __future__ import annotations

from typing import Any

import httpx

from app.core.config.settings import get_settings

APIFY_BASE = "https://api.apify.com/v2"


class SourceNotConfiguredError(RuntimeError):
    """Raised when a third-party marketplace connector lacks credentials."""


def apify_configured() -> bool:
    return bool(get_settings().apify_token)


async def run_actor(
    actor_id: str,
    actor_input: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    token = get_settings().apify_token
    if not token:
        raise SourceNotConfiguredError(
            "This connector uses an Apify community actor. Set APIFY_TOKEN to enable it."
        )

    actor_path = actor_id.replace("/", "~")
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        response = await client.post(
            f"{APIFY_BASE}/acts/{actor_path}/run-sync-get-dataset-items",
            params={"token": token, "clean": "true", "limit": limit},
            json=actor_input,
        )
        if response.status_code in {401, 403}:
            raise SourceNotConfiguredError("APIFY_TOKEN was rejected")
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected Apify response for {actor_id}")
    return [item for item in payload if isinstance(item, dict)][:limit]


async def search_peopleperhour(query: str, limit: int) -> list[dict[str, Any]]:
    settings = get_settings()
    rows = await run_actor(
        settings.peopleperhour_actor_id,
        {
            "mode": "searchJobs",
            "searchQuery": query,
            "maxItems": limit,
            "sortBy": "latest",
        },
        limit=limit,
    )
    return [_normalize_marketplace_row("peopleperhour", row) for row in rows]


async def search_guru(query: str, limit: int) -> list[dict[str, Any]]:
    settings = get_settings()
    rows = await run_actor(
        settings.guru_actor_id,
        {
            "searchType": "jobs",
            "keyword": query,
            "results_wanted": limit,
        },
        limit=limit,
    )
    return [_normalize_marketplace_row("guru", row) for row in rows]


def _normalize_marketplace_row(source: str, row: dict[str, Any]) -> dict[str, Any]:
    title = _first(row, "title", "jobTitle", "name", "projectTitle") or "Untitled"
    description = _first(
        row, "description", "jobDescription", "summary", "projectDescription"
    ) or title
    url = _first(row, "url", "jobUrl", "job_url", "projectUrl", "link") or ""
    source_id = _first(row, "id", "jobId", "job_id", "projectId", "slug", "url") or title
    company = _first(row, "company", "clientName", "buyerName", "employer") or (
        "PeoplePerHour client" if source == "peopleperhour" else "Guru client"
    )
    location = _first(row, "location", "clientLocation", "country") or "Remote"
    tags = _string_list(
        _first(row, "skills", "tags", "categories", "requiredSkills") or []
    )

    budget = row.get("budget")
    budget_min = _number(_first(row, "budgetMin", "minBudget", "minimum", "minPrice"))
    budget_max = _number(_first(row, "budgetMax", "maxBudget", "maximum", "maxPrice"))
    if isinstance(budget, dict):
        budget_min = budget_min or _number(
            _first(budget, "minimum", "min", "from", "minAmount")
        )
        budget_max = budget_max or _number(
            _first(budget, "maximum", "max", "to", "maxAmount")
        )

    return {
        "source_id": str(source_id),
        "title": str(title),
        "description": str(description),
        "url": str(url),
        "company": str(company),
        "budget_min": budget_min,
        "budget_max": budget_max,
        "posted_at": _first(
            row, "postedAt", "posted_at", "datePosted", "createdAt", "publishedAt"
        ),
        "tags": tags,
        "location": str(location),
    }


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip().lower() for part in value.split(",") if part.strip()]
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = _first(item, "name", "title", "label", "skill")
        if item:
            output.append(str(item).lower())
    return output


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
