from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from config.settings import get_settings
from app.core.security.oauth_state import create_upwork_oauth_state, validate_upwork_oauth_state
from app.ingestion.sources import (
    COMMERCIAL_FREE_SOURCES,
    COMMERCIAL_PRO_SOURCES,
    DISCOVERY_SOURCES,
    MARKETPLACE_SOURCES,
    PUBLIC_SOURCES,
    RESTRICTED_SOURCES,
    SOURCE_REGISTRY,
)
from app.integrations import apify_marketplaces
from app.integrations import freelancer as freelancer_api
from app.integrations import serpapi_discovery
from app.integrations import upwork as upwork_api

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status")
async def integrations_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "public_sources": list(PUBLIC_SOURCES),
        "marketplace_sources": list(MARKETPLACE_SOURCES),
        "discovery_sources": list(DISCOVERY_SOURCES),
        "commercial_free_sources": list(COMMERCIAL_FREE_SOURCES),
        "commercial_pro_sources": list(COMMERCIAL_PRO_SOURCES),
        "restricted_sources": list(RESTRICTED_SOURCES),
        "registered": list(SOURCE_REGISTRY.keys()),
        "notes": {
            "restricted": (
                "Remotive, We Work Remotely, PeoplePerHour, and Guru stay registered for demos "
                "but are blocked from commercial scrapes until licensed."
            ),
            "discovery": (
                "SerpAPI discovery covers freelance search, Google Jobs, curated company career "
                "sites (high-traffic ATS/aggregators filtered out), and Maps outreach. "
                "Requires SERPAPI_API_KEY and Pro. Company discovery searches allowlisted hosts "
                "only — it does not crawl HTML for contact info."
            ),
            "attribution": "Listings are shown as excerpts with source attribution and original apply links.",
        },
        "upwork": {
            "configured": upwork_api.upwork_configured(),
            "client_id_set": bool(settings.upwork_client_id),
            "authorize_path": "/integrations/upwork/authorize",
            "search_query": settings.upwork_search_query,
        },
        "freelancer": {
            "configured": freelancer_api.freelancer_configured(),
            "search_query": settings.freelancer_search_query,
        },
        "peopleperhour": {
            "configured": apify_marketplaces.apify_configured(),
            "provider": "apify_community_actor",
            "search_query": settings.peopleperhour_search_query,
        },
        "guru": {
            "configured": apify_marketplaces.apify_configured(),
            "provider": "apify_community_actor",
            "search_query": settings.guru_search_query,
        },
        "serpapi": {
            "configured": serpapi_discovery.serpapi_configured(),
            "freelance_query": settings.serpapi_freelance_query,
            "jobs_query": settings.serpapi_jobs_query,
            "companies_query": settings.serpapi_companies_query,
            "company_sites": serpapi_discovery.resolve_company_career_sites(),
            "company_site_batches": serpapi_discovery.build_companies_site_queries(
                keyword_query=settings.serpapi_companies_query
            ),
            "maps_query": settings.serpapi_maps_query,
            "maps_ll": settings.serpapi_maps_ll,
            "sources": list(DISCOVERY_SOURCES),
        },
        "unsupported": {
            "fiverr": (
                "Fiverr has no public client-job search API; its marketplace lists "
                "seller services rather than client opportunities."
            ),
            "contra": (
                "Contra has no public opportunities API or RSS feed. Existing "
                "community actors expose freelancer profiles, not a reliable jobs feed."
            ),
        },
    }


@router.get("/upwork/authorize")
async def upwork_authorize() -> RedirectResponse:
    try:
        state = create_upwork_oauth_state()
        url = upwork_api.build_authorize_url(state=state)
    except upwork_api.SourceNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url)


@router.get("/upwork/callback")
async def upwork_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> dict[str, object]:
    if error:
        raise HTTPException(status_code=400, detail=f"Upwork OAuth error: {error}")
    try:
        validate_upwork_oauth_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    try:
        tokens = await upwork_api.exchange_code_for_tokens(code)
    except upwork_api.SourceNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}") from exc

    return {
        "status": "connected",
        "token_type": tokens.token_type,
        "has_refresh_token": bool(tokens.refresh_token),
        "next": "POST /jobs/scrape with sources=['upwork']",
    }
