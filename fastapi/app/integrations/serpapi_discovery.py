from __future__ import annotations

import hashlib
import re
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from config.settings import get_settings
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"
Mode = Literal["freelance", "jobs", "maps", "companies"]

# Company-level career / tenant hosts (low-traffic ATS tenants included).
DEFAULT_COMPANY_CAREER_SITES: tuple[str, ...] = (
    "magnitglobal.com",
    "randstadusa.com",
    "peakperformers.org",
    "senecahq.com",
    "horizontaltalent.com",
    "apexsystems.com",
    "zeektek.com",
    "themomproject.com",
    "24seventalent.com",
    "codeclinch.com",
    "jobs.oiis.io",
    "wordpress.tential.com",
    "cephasconsult.biz",
    "experis.com",
    "bradhussey.ca",
    "lumieresystems.careers-page.com",
    "bakertilly.wd5.myworkdayjobs.com",
    "sparkbrighter-04a99f.careers.hibob.com",
    "spatial.zohorecruit.com",
    "globalcxaccenture.avature.net",
    "empattech.peopleforce.io",
    "indigoslate.applytojob.com",
    "homesmiles-careers.careerplug.com",
    "scig.oorwin.ai",
)

# High-traffic aggregators / ATS platforms — never accept as company careers hits.
HIGH_TRAFFIC_HOST_MARKERS: tuple[str, ...] = (
    "linkedin.com",
    "dice.com",
    "simplyhired.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "workable.com",
    "jobdiva.com",
    "ats.rippling.com",
    "rippling.com",
    "torre.ai",
    "wdtalenthub.com",
)

COMPANY_SITE_BATCH_SIZE = 8


class SourceNotConfiguredError(RuntimeError):
    """Raised when SerpAPI credentials are missing."""


def serpapi_configured() -> bool:
    return bool(get_settings().serpapi_api_key)


def normalize_company_host(value: str) -> str:
    host = value.strip().lower()
    host = host.removeprefix("https://").removeprefix("http://")
    host = host.split("/", 1)[0]
    return host.removeprefix("www.")


def resolve_company_career_sites(raw: str | None = None) -> list[str]:
    """Return curated company hosts; env override replaces the built-in list when set."""
    if raw is None:
        raw = get_settings().serpapi_company_sites
    if raw and raw.strip():
        sites = [normalize_company_host(part) for part in raw.split(",") if part.strip()]
        return list(dict.fromkeys(site for site in sites if site))
    return list(DEFAULT_COMPANY_CAREER_SITES)


def build_companies_site_queries(
    *,
    keyword_query: str,
    sites: list[str] | None = None,
    batch_size: int = COMPANY_SITE_BATCH_SIZE,
) -> list[str]:
    """Combine skill/careers keywords with batched site: filters."""
    keyword = keyword_query.strip() or (
        '(careers OR "we\'re hiring" OR "open roles" OR jobs) (python OR fastapi OR react)'
    )
    hosts = sites if sites is not None else resolve_company_career_sites()
    if not hosts:
        return [keyword]
    size = max(batch_size, 1)
    queries: list[str] = []
    for index in range(0, len(hosts), size):
        batch = hosts[index : index + size]
        site_clause = " OR ".join(f"site:{host}" for host in batch)
        queries.append(f"{keyword} ({site_clause})")
    return queries


def _stable_id(url: str, title: str) -> str:
    digest = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]
    return digest


def _hostname(url: str) -> str | None:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return None
    return host.lower().removeprefix("www.") or None


def _host_matches(host: str | None, markers: tuple[str, ...] | list[str]) -> bool:
    if not host:
        return False
    for marker in markers:
        marker_host = normalize_company_host(marker)
        if not marker_host:
            continue
        if host == marker_host or host.endswith("." + marker_host):
            return True
    return False


def _looks_useful_freelance(title: str, snippet: str, link: str) -> bool:
    blob = f"{title} {snippet} {link}".lower()
    positive = (
        "freelance",
        "freelancer",
        "contractor",
        "contract",
        "hire",
        "hiring",
        "looking for",
        "need a",
        "seeking",
        "gig",
        "remote",
        "project",
    )
    noise = (
        "salary guide",
        "how to become",
        "course",
        "tutorial",
        "what is a freelancer",
        "best freelance websites",
    )
    if any(token in blob for token in noise):
        return False
    return any(token in blob for token in positive)


def _looks_like_company_careers(
    title: str,
    snippet: str,
    link: str,
    *,
    company_sites: list[str] | None = None,
) -> bool:
    host = _hostname(link)
    if _host_matches(host, HIGH_TRAFFIC_HOST_MARKERS):
        return False

    allowlist = company_sites if company_sites is not None else resolve_company_career_sites()
    if _host_matches(host, allowlist):
        return True

    blob = f"{title} {snippet} {link}".lower()
    path_hits = (
        "/careers",
        "/career",
        "/jobs",
        "/job/",
        "/join-us",
        "/joinus",
        "/openings",
        "/vacancies",
    )
    text_hits = (
        "we're hiring",
        "we are hiring",
        "open roles",
        "open positions",
        "join our team",
        "career opportunities",
        "job openings",
    )
    return any(token in blob for token in path_hits) or any(token in blob for token in text_hits)


async def search_discovery(
    *,
    mode: Mode,
    query: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    settings = get_settings()
    api_key = settings.serpapi_api_key
    if not api_key:
        raise SourceNotConfiguredError(
            "SerpAPI is not configured. Set SERPAPI_API_KEY in the environment."
        )

    if mode == "freelance":
        search_query = (query or settings.serpapi_freelance_query).strip()
        return await _search_google_organic(
            api_key=api_key,
            query=search_query,
            limit=limit,
            mode="freelance",
            gl=settings.serpapi_gl,
            hl=settings.serpapi_hl,
        )

    if mode == "companies":
        if query and query.strip():
            return await _search_google_organic(
                api_key=api_key,
                query=query.strip(),
                limit=limit,
                mode="companies",
                gl=settings.serpapi_gl,
                hl=settings.serpapi_hl,
                company_sites=resolve_company_career_sites(),
            )
        return await _search_companies_batched(
            api_key=api_key,
            keyword_query=settings.serpapi_companies_query,
            limit=limit,
            gl=settings.serpapi_gl,
            hl=settings.serpapi_hl,
        )

    if mode == "maps":
        search_query = (query or settings.serpapi_maps_query).strip()
        return await _search_google_maps(
            api_key=api_key,
            query=search_query,
            limit=limit,
            ll=settings.serpapi_maps_ll,
            hl=settings.serpapi_hl,
        )

    search_query = (query or settings.serpapi_jobs_query).strip()
    return await _search_google_jobs(
        api_key=api_key,
        query=search_query,
        limit=limit,
        location=settings.serpapi_location,
        gl=settings.serpapi_gl,
        hl=settings.serpapi_hl,
    )


async def _search_companies_batched(
    *,
    api_key: str,
    keyword_query: str,
    limit: int,
    gl: str,
    hl: str,
) -> list[dict[str, Any]]:
    sites = resolve_company_career_sites()
    queries = build_companies_site_queries(keyword_query=keyword_query, sites=sites)
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for search_query in queries:
        batch_rows = await _search_google_organic(
            api_key=api_key,
            query=search_query,
            limit=limit,
            mode="companies",
            gl=gl,
            hl=hl,
            company_sites=sites,
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


async def _search_google_organic(
    *,
    api_key: str,
    query: str,
    limit: int,
    mode: Mode,
    gl: str,
    hl: str,
    company_sites: list[str] | None = None,
) -> list[dict[str, Any]]:
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "gl": gl,
        "hl": hl,
        "num": min(max(limit, 1), 20),
    }
    payload = await _get_json(params)
    rows: list[dict[str, Any]] = []
    for item in payload.get("organic_results") or []:
        title = str(item.get("title") or "Untitled").strip()
        link = str(item.get("link") or "").strip()
        snippet = str(item.get("snippet") or item.get("about_this_result") or title).strip()
        if not link:
            continue
        if mode == "freelance" and not _looks_useful_freelance(title, snippet, link):
            continue
        if mode == "companies" and not _looks_like_company_careers(
            title, snippet, link, company_sites=company_sites
        ):
            continue
        host = _hostname(link)
        location = "Company careers page" if mode == "companies" else "Remote / web discovery"
        rows.append(
            {
                "source_id": _stable_id(link, title),
                "title": title,
                "description": snippet,
                "url": link,
                "company": host,
                "budget_min": None,
                "budget_max": None,
                "posted_at": item.get("date"),
                "tags": ["discovery", "serpapi", mode, *([host] if host else [])],
                "location": location,
                "metadata": {
                    "discovery_mode": mode,
                    "engine": "google",
                    "query": query,
                    "position": item.get("position"),
                    "displayed_link": item.get("displayed_link"),
                },
            }
        )
        if len(rows) >= limit:
            break
    return rows


async def _search_google_maps(
    *,
    api_key: str,
    query: str,
    limit: int,
    ll: str,
    hl: str,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "engine": "google_maps",
        "type": "search",
        "q": query,
        "api_key": api_key,
        "hl": hl,
    }
    if ll.strip():
        params["ll"] = ll.strip()
    payload = await _get_json(params)
    rows: list[dict[str, Any]] = []
    for item in payload.get("local_results") or []:
        title = str(item.get("title") or "Untitled").strip()
        website = str(item.get("website") or "").strip()
        place_id = str(item.get("place_id") or item.get("data_id") or "").strip()
        maps_link = ""
        if place_id:
            maps_link = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        phone = str(item.get("phone") or "").strip()
        # Prefer businesses with a contact surface (site or phone).
        if not website and not phone:
            continue
        link = website or maps_link
        if not link:
            continue
        address = str(item.get("address") or "").strip()
        place_type = item.get("type")
        types = item.get("types") if isinstance(item.get("types"), list) else []
        rating = item.get("rating")
        reviews = item.get("reviews")
        description_parts = [
            f"Local outreach lead: {title}.",
            f"Type: {place_type}." if place_type else "",
            f"Address: {address}." if address else "",
            f"Phone: {phone}." if phone else "",
            f"Website: {website}." if website else "",
            f"Rating: {rating} ({reviews} reviews)." if rating is not None else "",
            str(item.get("description") or "").strip(),
        ]
        description = " ".join(part for part in description_parts if part)
        tags = ["discovery", "serpapi", "maps", "outreach"]
        if isinstance(place_type, str) and place_type:
            tags.append(place_type.lower())
        for entry in types[:4]:
            if isinstance(entry, str) and entry.strip():
                tags.append(entry.strip().lower())
        rows.append(
            {
                "source_id": place_id or _stable_id(link, title),
                "title": f"Outreach: {title}",
                "description": description[:4000],
                "url": link,
                "company": title,
                "budget_min": None,
                "budget_max": None,
                "posted_at": None,
                "tags": tags[:12],
                "location": address or "Local business",
                "metadata": {
                    "discovery_mode": "maps",
                    "engine": "google_maps",
                    "query": query,
                    "phone": phone or None,
                    "website": website or None,
                    "maps_url": maps_link or None,
                    "rating": rating,
                    "reviews": reviews,
                    "place_id": place_id or None,
                },
            }
        )
        if len(rows) >= limit:
            break
    return rows


async def _search_google_jobs(
    *,
    api_key: str,
    query: str,
    limit: int,
    location: str,
    gl: str,
    hl: str,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "engine": "google_jobs",
        "q": query,
        "api_key": api_key,
        "gl": gl,
        "hl": hl,
    }
    if location:
        params["location"] = location
    payload = await _get_json(params)
    rows: list[dict[str, Any]] = []
    for item in payload.get("jobs_results") or []:
        title = str(item.get("title") or "Untitled").strip()
        company = item.get("company_name")
        description = str(item.get("description") or item.get("share_link") or title).strip()
        apply_options = item.get("apply_options") or []
        link = ""
        if isinstance(apply_options, list) and apply_options:
            first = apply_options[0] if isinstance(apply_options[0], dict) else {}
            link = str(first.get("link") or "")
        if not link:
            link = str(item.get("share_link") or item.get("link") or "").strip()
        if not link:
            # Stable fallback so ingest still has a URL-like identity.
            link = f"https://www.google.com/search?q={re.sub(r'\s+', '+', title)}"
        location_label = None
        locations = item.get("location") or item.get("locations")
        if isinstance(locations, str):
            location_label = locations
        elif isinstance(locations, list) and locations:
            location_label = ", ".join(str(part) for part in locations[:3])

        extensions = item.get("detected_extensions") or {}
        schedule = extensions.get("schedule_type") if isinstance(extensions, dict) else None
        tags = ["discovery", "serpapi", "jobs"]
        if schedule:
            tags.append(str(schedule).lower())
        for ext in item.get("extensions") or []:
            if isinstance(ext, str) and ext.strip():
                tags.append(ext.strip().lower())

        rows.append(
            {
                "source_id": str(item.get("job_id") or _stable_id(link, title)),
                "title": title,
                "description": description[:4000],
                "url": link,
                "company": company,
                "budget_min": None,
                "budget_max": None,
                "posted_at": (extensions or {}).get("posted_at") if isinstance(extensions, dict) else None,
                "tags": tags[:12],
                "location": location_label or "Remote / unspecified",
                "metadata": {
                    "discovery_mode": "jobs",
                    "engine": "google_jobs",
                    "query": query,
                    "via": item.get("via"),
                },
            }
        )
        if len(rows) >= limit:
            break
    return rows


async def _get_json(params: dict[str, Any]) -> dict[str, Any]:
    headers = {"User-Agent": "FreelanceIntelligence/0.5 (+serpapi)"}
    async with httpx.AsyncClient(timeout=45.0, headers=headers, follow_redirects=True) as client:
        response = await client.get(SERPAPI_URL, params=params)
        if response.status_code in {401, 403}:
            raise SourceNotConfiguredError("SerpAPI key rejected (401/403)")
        response.raise_for_status()
        payload = response.json()
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload if isinstance(payload, dict) else {}
