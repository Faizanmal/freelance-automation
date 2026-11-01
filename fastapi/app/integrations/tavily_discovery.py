from __future__ import annotations

from typing import Any, Literal

import httpx

from app.core.logging.logger import get_logger
from app.integrations.serpapi_discovery import (
    ATS_DISCOVERY_SITES,
    HIGH_TRAFFIC_HOST_MARKERS,
    Mode,
    SourceNotConfiguredError,
    _hostname,
    _looks_like_company_careers,
    _looks_useful_freelance,
    _stable_id,
    normalize_company_host,
    resolve_company_career_sites,
)
from config.settings import get_settings

logger = get_logger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
COMPANY_DOMAIN_BATCH_SIZE = 20

# Aggregators Tavily should skip for company/freelance discovery noise.
DEFAULT_EXCLUDE_DOMAINS: tuple[str, ...] = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "dice.com",
    "simplyhired.com",
    "youtube.com",
    "wikipedia.org",
)


def tavily_configured() -> bool:
    key = get_settings().tavily_api_key
    return isinstance(key, str) and bool(key.strip())


async def search_discovery(
    *,
    mode: Mode,
    query: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search via Tavily. Maps mode is not supported (SerpAPI-only)."""
    if mode == "maps":
        raise SourceNotConfiguredError(
            "Tavily does not support maps discovery; use SerpAPI for serpapi_maps."
        )

    settings = get_settings()
    api_key = settings.tavily_api_key
    if not isinstance(api_key, str) or not api_key.strip():
        raise SourceNotConfiguredError(
            "Tavily is not configured. Set TAVILY_API_KEY in the environment."
        )

    if mode == "freelance":
        search_query = (query or settings.serpapi_freelance_query).strip()
        if not search_query:
            raise SourceNotConfiguredError(
                "Freelance query is empty. Set SERPAPI_FREELANCE_QUERY."
            )
        return await _search_web(
            api_key=api_key.strip(),
            query=search_query,
            limit=limit,
            mode="freelance",
            search_depth=settings.tavily_search_depth,
            exclude_domains=list(DEFAULT_EXCLUDE_DOMAINS),
        )

    if mode == "companies":
        if query and query.strip():
            return await _search_web(
                api_key=api_key.strip(),
                query=query.strip(),
                limit=limit,
                mode="companies",
                search_depth=settings.tavily_search_depth,
                company_sites=resolve_company_career_sites(),
                exclude_domains=list(HIGH_TRAFFIC_HOST_MARKERS),
            )
        return await _search_companies_batched(
            api_key=api_key.strip(),
            keyword_query=settings.serpapi_companies_query,
            limit=limit,
            search_depth=settings.tavily_search_depth,
        )

    # jobs — organic web search; SerpAPI Google Jobs remains the fallback engine
    search_query = (query or settings.serpapi_jobs_query).strip()
    if not search_query:
        raise SourceNotConfiguredError(
            "Jobs query is empty. Set SERPAPI_JOBS_QUERY."
        )
    return await _search_web(
        api_key=api_key.strip(),
        query=search_query,
        limit=limit,
        mode="jobs",
        search_depth=settings.tavily_search_depth,
        exclude_domains=["youtube.com", "wikipedia.org"],
    )


async def _search_companies_batched(
    *,
    api_key: str,
    keyword_query: str,
    limit: int,
    search_depth: str,
) -> list[dict[str, Any]]:
    sites = resolve_company_career_sites()
    keyword = keyword_query.strip() or (
        '(careers OR "we\'re hiring" OR "open roles" OR jobs) '
        "(python OR fastapi OR react)"
    )
    if not sites:
        return await _search_web(
            api_key=api_key,
            query=keyword,
            limit=limit,
            mode="companies",
            search_depth=search_depth,
            company_sites=sites,
            exclude_domains=list(HIGH_TRAFFIC_HOST_MARKERS),
        )

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    size = max(COMPANY_DOMAIN_BATCH_SIZE, 1)
    for index in range(0, len(sites), size):
        batch = sites[index : index + size]
        batch_rows = await _search_web(
            api_key=api_key,
            query=keyword,
            limit=limit,
            mode="companies",
            search_depth=search_depth,
            include_domains=batch,
            company_sites=sites,
            exclude_domains=list(HIGH_TRAFFIC_HOST_MARKERS),
        )
        for row in batch_rows:
            key = str(row.get("url") or row.get("source_id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(row)
            if len(merged) >= limit:
                return merged
    return merged


async def _search_web(
    *,
    api_key: str,
    query: str,
    limit: int,
    mode: Literal["freelance", "jobs", "companies"],
    search_depth: str,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    company_sites: list[str] | None = None,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {
        "query": query,
        "max_results": min(max(limit, 1), 20),
        "search_depth": search_depth if search_depth in {"basic", "advanced", "fast", "ultra-fast"} else "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    if include_domains:
        body["include_domains"] = [
            normalize_company_host(host) for host in include_domains if host.strip()
        ][:300]
    if exclude_domains:
        body["exclude_domains"] = [
            normalize_company_host(host) for host in exclude_domains if host.strip()
        ][:300]

    payload = await _post_json(api_key=api_key, body=body)
    rows: list[dict[str, Any]] = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Untitled").strip()
        link = str(item.get("url") or "").strip()
        snippet = str(item.get("content") or title).strip()
        if not link:
            continue
        if mode == "freelance" and not _looks_useful_freelance(title, snippet, link):
            continue
        if mode == "companies" and not _looks_like_company_careers(
            title, snippet, link, company_sites=company_sites
        ):
            continue

        host = _hostname(link)
        location = (
            "Company careers page" if mode == "companies" else "Remote / web discovery"
        )
        score = item.get("score")
        tags = ["discovery", "tavily", mode, *([host] if host else [])]
        if mode == "companies" and _hostname(link) and any(
            _hostname(link) == normalize_company_host(s)
            or (_hostname(link) or "").endswith("." + normalize_company_host(s))
            for s in ATS_DISCOVERY_SITES
        ):
            tags.append("ats")

        rows.append(
            {
                "source_id": _stable_id(link, title),
                "title": title,
                "description": snippet[:4000],
                "url": link,
                "company": host,
                "budget_min": None,
                "budget_max": None,
                "posted_at": item.get("published_date"),
                "tags": tags[:12],
                "location": location,
                "metadata": {
                    "discovery_mode": mode,
                    "engine": "tavily",
                    "provider": "tavily",
                    "query": query,
                    "score": score,
                },
            }
        )
        if len(rows) >= limit:
            break
    return rows


async def _post_json(*, api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "SignalDesk/0.5 (+tavily)",
    }
    async with httpx.AsyncClient(
        timeout=45.0, headers=headers, follow_redirects=True
    ) as client:
        response = await client.post(TAVILY_URL, json=body)
        if response.status_code in {401, 403}:
            raise SourceNotConfiguredError("Tavily key rejected (401/403)")
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {}
