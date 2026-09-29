from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

import httpx

from backend.application.services.duplicate_detection import JobCandidate


class RemoteOKSource:
    """Fetch live jobs from RemoteOK's public JSON API."""

    name = "remoteok"
    url = "https://remoteok.com/api"

    async def fetch(self, *, limit: int = 50, tags: list[str] | None = None) -> list[JobCandidate]:
        headers = {"User-Agent": "FreelanceIntelligence/0.2 (+local)"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            payload = response.json()

        wanted = {tag.lower() for tag in (tags or [])}
        jobs: list[JobCandidate] = []
        for row in payload:
            if not isinstance(row, dict) or "id" not in row or "position" not in row:
                continue
            job_tags = [str(tag).lower() for tag in (row.get("tags") or [])]
            if wanted and not wanted.intersection(job_tags):
                continue

            posted_at = None
            epoch = row.get("epoch") or row.get("date")
            if isinstance(epoch, (int, float)):
                posted_at = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
            elif isinstance(epoch, str) and epoch:
                posted_at = epoch

            jobs.append(
                JobCandidate(
                    source_name=self.name,
                    source_id=str(row["id"]),
                    title=str(row.get("position") or "Untitled"),
                    description=str(row.get("description") or row.get("position") or ""),
                    url=str(row.get("url") or f"https://remoteok.com/remote-jobs/{row['id']}"),
                    company=row.get("company"),
                    budget_min=_to_float(row.get("salary_min")),
                    budget_max=_to_float(row.get("salary_max")),
                    posted_at=posted_at,
                    metadata={"location": row.get("location") or "Remote", "tags": job_tags},
                )
            )
            if len(jobs) >= limit:
                break
        return jobs


class RemotiveSource:
    """Fetch live remote jobs from Remotive's public API."""

    name = "remotive"
    url = "https://remotive.com/api/remote-jobs"

    async def fetch(self, *, limit: int = 50, category: str | None = None) -> list[JobCandidate]:
        params: dict[str, Any] = {"limit": limit}
        if category:
            params["category"] = category
        headers = {"User-Agent": "FreelanceIntelligence/0.2 (+local)"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.url, params=params)
            response.raise_for_status()
            payload = response.json()

        jobs: list[JobCandidate] = []
        for row in payload.get("jobs") or []:
            tags = [str(tag).lower() for tag in (row.get("tags") or [])]
            jobs.append(
                JobCandidate(
                    source_name=self.name,
                    source_id=str(row.get("id")),
                    title=str(row.get("title") or "Untitled"),
                    description=str(row.get("description") or ""),
                    url=str(row.get("url") or row.get("job_url") or ""),
                    company=row.get("company_name"),
                    budget_min=None,
                    budget_max=None,
                    posted_at=row.get("publication_date"),
                    metadata={
                        "location": row.get("candidate_required_location") or "Remote",
                        "tags": tags,
                        "category": row.get("category"),
                    },
                )
            )
            if len(jobs) >= limit:
                break
        return jobs


class ArbeitnowSource:
    """Fetch jobs from Arbeitnow's public API."""

    name = "arbeitnow"
    url = "https://www.arbeitnow.com/api/job-board-api"

    async def fetch(self, *, limit: int = 50) -> list[JobCandidate]:
        headers = {"User-Agent": "FreelanceIntelligence/0.2 (+local)"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            payload = response.json()

        jobs: list[JobCandidate] = []
        for row in payload.get("data") or []:
            tags = [str(tag).lower() for tag in (row.get("tags") or [])]
            skill_tags = [str(tag).lower() for tag in (row.get("job_types") or [])]
            posted_at = None
            created = row.get("created_at")
            if isinstance(created, (int, float)):
                posted_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
            elif isinstance(created, str) and created:
                posted_at = created

            slug = row.get("slug") or row.get("url") or row.get("title")
            jobs.append(
                JobCandidate(
                    source_name=self.name,
                    source_id=str(slug),
                    title=str(row.get("title") or "Untitled"),
                    description=str(row.get("description") or ""),
                    url=str(row.get("url") or f"https://www.arbeitnow.com/view/{slug}"),
                    company=row.get("company_name"),
                    budget_min=None,
                    budget_max=None,
                    posted_at=posted_at,
                    metadata={
                        "location": row.get("location") or "Remote",
                        "tags": list({*tags, *skill_tags}),
                        "remote": bool(row.get("remote")),
                    },
                )
            )
            if len(jobs) >= limit:
                break
        return jobs


class WeWorkRemotelySource:
    """Fetch listings from We Work Remotely's official public RSS feed."""

    name = "weworkremotely"
    url = "https://weworkremotely.com/remote-jobs.rss"

    async def fetch(self, *, limit: int = 50) -> list[JobCandidate]:
        headers = {"User-Agent": "FreelanceIntelligence/0.4 (+local)"}
        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            response = await client.get(self.url)
            response.raise_for_status()

        root = ElementTree.fromstring(response.content)
        jobs: list[JobCandidate] = []
        for item in root.findall(".//item"):
            raw_title = _xml_text(item, "title") or "Untitled"
            company, title = _split_company_title(raw_title)
            url = _xml_text(item, "link") or ""
            source_id = _xml_text(item, "guid") or url or raw_title
            description = _xml_text(item, "description") or title
            jobs.append(
                JobCandidate(
                    source_name=self.name,
                    source_id=source_id,
                    title=title,
                    description=description,
                    url=url,
                    company=company,
                    posted_at=_xml_text(item, "pubDate"),
                    metadata={
                        "location": _xml_namespaced_text(item, "region") or "Remote",
                        "tags": [
                            value.lower()
                            for value in (
                                _xml_namespaced_text(item, "type"),
                                _xml_namespaced_text(item, "category"),
                            )
                            if value
                        ],
                    },
                )
            )
            if len(jobs) >= limit:
                break
        return jobs


class HimalayasSource:
    """Fetch remote jobs from Himalayas' free public JSON API (no auth)."""

    name = "himalayas"
    url = "https://himalayas.app/jobs/api"
    page_size = 20

    async def fetch(self, *, limit: int = 50) -> list[JobCandidate]:
        headers = {"User-Agent": "FreelanceIntelligence/0.4 (+local)"}
        jobs: list[JobCandidate] = []
        offset = 0
        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            while len(jobs) < limit:
                page_limit = min(self.page_size, limit - len(jobs))
                response = await client.get(
                    self.url, params={"offset": offset, "limit": page_limit}
                )
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("jobs") or []
                if not rows:
                    break
                for row in rows:
                    guid = row.get("guid") or row.get("applicationLink") or row.get("title")
                    location = row.get("locationRestrictions") or []
                    if isinstance(location, list):
                        location_label = ", ".join(str(item) for item in location) or "Remote"
                    else:
                        location_label = str(location) or "Remote"
                    tags = [
                        str(tag).lower()
                        for tag in (
                            *(row.get("categories") or []),
                            *(row.get("parentCategories") or []),
                            *((row.get("seniority") or []) if isinstance(row.get("seniority"), list) else []),
                            row.get("employmentType"),
                        )
                        if tag
                    ]
                    posted_at = row.get("pubDate")
                    if isinstance(posted_at, (int, float)):
                        posted_at = datetime.fromtimestamp(posted_at, tz=timezone.utc).isoformat()
                    jobs.append(
                        JobCandidate(
                            source_name=self.name,
                            source_id=str(guid),
                            title=str(row.get("title") or "Untitled"),
                            description=str(
                                row.get("description") or row.get("excerpt") or row.get("title") or ""
                            ),
                            url=str(
                                row.get("applicationLink")
                                or row.get("guid")
                                or ""
                            ),
                            company=row.get("companyName"),
                            budget_min=_to_float(row.get("minSalary")),
                            budget_max=_to_float(row.get("maxSalary")),
                            posted_at=str(posted_at) if posted_at else None,
                            metadata={
                                "location": location_label,
                                "tags": tags,
                                "currency": row.get("currency"),
                                "salary_period": row.get("salaryPeriod"),
                            },
                        )
                    )
                    if len(jobs) >= limit:
                        break
                offset += len(rows)
                if len(rows) < page_limit:
                    break
        return jobs


class JobicySource:
    """Fetch remote jobs from Jobicy's free public JSON API (no auth)."""

    name = "jobicy"
    url = "https://jobicy.com/api/v2/remote-jobs"

    async def fetch(self, *, limit: int = 50, tag: str | None = None) -> list[JobCandidate]:
        params: dict[str, Any] = {"count": min(max(limit, 1), 100)}
        if tag:
            params["tag"] = tag
        headers = {"User-Agent": "FreelanceIntelligence/0.4 (+local)"}
        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            response = await client.get(self.url, params=params)
            response.raise_for_status()
            payload = response.json()

        jobs: list[JobCandidate] = []
        for row in payload.get("jobs") or []:
            industry = row.get("jobIndustry") or []
            job_type = row.get("jobType") or []
            if not isinstance(industry, list):
                industry = [industry] if industry else []
            if not isinstance(job_type, list):
                job_type = [job_type] if job_type else []
            tags = [
                str(tag).lower()
                for tag in (*industry, *job_type, row.get("jobLevel"))
                if tag
            ]
            jobs.append(
                JobCandidate(
                    source_name=self.name,
                    source_id=str(row.get("id") or row.get("jobSlug") or row.get("url")),
                    title=str(row.get("jobTitle") or "Untitled"),
                    description=str(
                        row.get("jobDescription")
                        or row.get("jobExcerpt")
                        or row.get("jobTitle")
                        or ""
                    ),
                    url=str(row.get("url") or ""),
                    company=row.get("companyName"),
                    budget_min=_to_float(row.get("salaryMin")),
                    budget_max=_to_float(row.get("salaryMax")),
                    posted_at=row.get("pubDate"),
                    metadata={
                        "location": row.get("jobGeo") or "Remote",
                        "tags": tags,
                        "currency": row.get("salaryCurrency"),
                        "salary_period": row.get("salaryPeriod"),
                    },
                )
            )
            if len(jobs) >= limit:
                break
        return jobs


class UpworkSource:
    """Fetch jobs via Upwork's official GraphQL API (OAuth required)."""

    name = "upwork"

    async def fetch(self, *, limit: int = 50, query: str | None = None) -> list[JobCandidate]:
        from app.integrations import upwork as upwork_api
        from config.settings import get_settings

        settings = get_settings()
        search_query = query or settings.upwork_search_query
        rows = await upwork_api.search_jobs(query=search_query, limit=limit)
        return [
            JobCandidate(
                source_name=self.name,
                source_id=row["source_id"],
                title=row["title"],
                description=row["description"],
                url=row["url"],
                company=row.get("company"),
                budget_min=row.get("budget_min"),
                budget_max=row.get("budget_max"),
                posted_at=row.get("posted_at"),
                metadata={"location": row.get("location") or "Remote", "tags": row.get("tags") or []},
            )
            for row in rows
        ]


class FreelancerSource:
    """Fetch active projects via Freelancer.com official API (OAuth token required)."""

    name = "freelancer"

    async def fetch(self, *, limit: int = 50, query: str | None = None) -> list[JobCandidate]:
        from app.integrations import freelancer as freelancer_api
        from config.settings import get_settings

        settings = get_settings()
        search_query = query or settings.freelancer_search_query
        rows = await freelancer_api.search_projects(query=search_query, limit=limit)
        return [
            JobCandidate(
                source_name=self.name,
                source_id=row["source_id"],
                title=row["title"],
                description=row["description"],
                url=row["url"],
                company=row.get("company"),
                budget_min=row.get("budget_min"),
                budget_max=row.get("budget_max"),
                posted_at=row.get("posted_at"),
                metadata={"location": row.get("location") or "Remote", "tags": row.get("tags") or []},
            )
            for row in rows
        ]


class PeoplePerHourSource:
    """PeoplePerHour job connector through a configured Apify actor."""

    name = "peopleperhour"

    async def fetch(
        self, *, limit: int = 50, query: str | None = None
    ) -> list[JobCandidate]:
        from app.integrations.apify_marketplaces import search_peopleperhour
        from config.settings import get_settings

        settings = get_settings()
        rows = await search_peopleperhour(
            query or settings.peopleperhour_search_query, limit
        )
        return [_candidate_from_row(self.name, row) for row in rows]


class GuruSource:
    """Guru job connector through a configured Apify actor."""

    name = "guru"

    async def fetch(
        self, *, limit: int = 50, query: str | None = None
    ) -> list[JobCandidate]:
        from app.integrations.apify_marketplaces import search_guru
        from config.settings import get_settings

        settings = get_settings()
        rows = await search_guru(query or settings.guru_search_query, limit)
        return [_candidate_from_row(self.name, row) for row in rows]


class SerpApiFreelanceSource:
    """Discover freelance-style opportunities via SerpAPI Google organic search."""

    name = "serpapi_freelance"

    async def fetch(
        self, *, limit: int = 20, query: str | None = None
    ) -> list[JobCandidate]:
        from app.integrations import serpapi_discovery

        rows = await serpapi_discovery.search_discovery(
            mode="freelance", query=query, limit=limit
        )
        return [_candidate_from_row(self.name, row) for row in rows]


class SerpApiJobsSource:
    """Discover job listings via SerpAPI Google Jobs engine."""

    name = "serpapi_jobs"

    async def fetch(
        self, *, limit: int = 20, query: str | None = None
    ) -> list[JobCandidate]:
        from app.integrations import serpapi_discovery

        rows = await serpapi_discovery.search_discovery(
            mode="jobs", query=query, limit=limit
        )
        return [_candidate_from_row(self.name, row) for row in rows]


class SerpApiCompaniesSource:
    """Discover company career pages via SerpAPI Google organic search."""

    name = "serpapi_companies"

    async def fetch(
        self, *, limit: int = 20, query: str | None = None
    ) -> list[JobCandidate]:
        from app.integrations import serpapi_discovery

        rows = await serpapi_discovery.search_discovery(
            mode="companies", query=query, limit=limit
        )
        return [_candidate_from_row(self.name, row) for row in rows]


class SerpApiMapsSource:
    """Discover local outreach leads via SerpAPI Google Maps."""

    name = "serpapi_maps"

    async def fetch(
        self, *, limit: int = 20, query: str | None = None
    ) -> list[JobCandidate]:
        from app.integrations import serpapi_discovery

        rows = await serpapi_discovery.search_discovery(
            mode="maps", query=query, limit=limit
        )
        return [_candidate_from_row(self.name, row) for row in rows]


def _candidate_from_row(source: str, row: dict[str, Any]) -> JobCandidate:
    extra = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return JobCandidate(
        source_name=source,
        source_id=row["source_id"],
        title=row["title"],
        description=row["description"],
        url=row["url"],
        company=row.get("company"),
        budget_min=row.get("budget_min"),
        budget_max=row.get("budget_max"),
        posted_at=row.get("posted_at"),
        metadata={
            "location": row.get("location") or "Remote",
            "tags": row.get("tags") or [],
            **extra,
        },
    )


def _xml_text(item: ElementTree.Element, tag: str) -> str | None:
    node = item.find(tag)
    if node is None or node.text is None:
        return None
    return node.text.strip()


def _xml_namespaced_text(item: ElementTree.Element, local_name: str) -> str | None:
    for child in item:
        if child.tag.rsplit("}", 1)[-1] == local_name and child.text:
            return child.text.strip()
    return None


def _split_company_title(value: str) -> tuple[str | None, str]:
    if ":" not in value:
        return None, value.strip()
    company, title = value.split(":", 1)
    return company.strip() or None, title.strip() or value.strip()


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class LinkedInBrowserSource:
    name = "linkedin_browser"

    async def fetch(self, *, limit: int = 20, query: str | None = None) -> list[JobCandidate]:
        import os
        import sys
        # Ensure scrapers module is accessible
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            
        from scrapers.core.browser_engine import BrowserEngine
        from scrapers.sources.linkedin_browser import LinkedInBrowserScraper
        
        engine = BrowserEngine(headless=True)
        await engine.start()
        
        try:
            page = await engine.new_page()
            scraper = LinkedInBrowserScraper(engine=engine, page=page)
            raw_jobs = await scraper.fetch_jobs(limit=limit, query=query or "software engineer")
            candidates = []
            for raw in raw_jobs:
                candidates.append(
                    JobCandidate(
                        source_name=self.name,
                        source_id=raw["url"],
                        title=raw["title"],
                        description=raw.get("description", ""),
                        url=raw["url"],
                        company=raw.get("company", "Unknown"),
                        budget_min=None,
                        budget_max=None,
                        posted_at=None,
                        metadata={"location": "Remote", "tags": []}
                    )
                )
            return candidates
        finally:
            await engine.stop()


class UpworkBrowserSource:
    name = "upwork_browser"

    async def fetch(self, *, limit: int = 20, query: str | None = None) -> list[JobCandidate]:
        import os
        import sys
        # Ensure scrapers module is accessible
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            
        from scrapers.core.browser_engine import BrowserEngine
        from scrapers.sources.upwork_browser import UpworkBrowserScraper
        
        engine = BrowserEngine(headless=True)
        await engine.start()
        
        try:
            page = await engine.new_page()
            scraper = UpworkBrowserScraper(engine=engine, page=page)
            raw_jobs = await scraper.fetch_jobs(limit=limit, query=query or "python developer")
            candidates = []
            for raw in raw_jobs:
                candidates.append(
                    JobCandidate(
                        source_name=self.name,
                        source_id=raw["url"],
                        title=raw["title"],
                        description=raw.get("description", ""),
                        url=raw["url"],
                        company="Upwork client",
                        budget_min=None,
                        budget_max=None,
                        posted_at=None,
                        metadata={"location": "Remote", "tags": []}
                    )
                )
            return candidates
        finally:
            await engine.stop()


SOURCE_REGISTRY = {
    RemoteOKSource.name: RemoteOKSource,
    RemotiveSource.name: RemotiveSource,
    ArbeitnowSource.name: ArbeitnowSource,
    WeWorkRemotelySource.name: WeWorkRemotelySource,
    HimalayasSource.name: HimalayasSource,
    JobicySource.name: JobicySource,
    UpworkSource.name: UpworkSource,
    FreelancerSource.name: FreelancerSource,
    PeoplePerHourSource.name: PeoplePerHourSource,
    GuruSource.name: GuruSource,
    SerpApiFreelanceSource.name: SerpApiFreelanceSource,
    SerpApiJobsSource.name: SerpApiJobsSource,
    SerpApiCompaniesSource.name: SerpApiCompaniesSource,
    SerpApiMapsSource.name: SerpApiMapsSource,
    LinkedInBrowserSource.name: LinkedInBrowserSource,
    UpworkBrowserSource.name: UpworkBrowserSource,
}

PUBLIC_SOURCES = (
    "remoteok",
    "remotive",
    "arbeitnow",
    "weworkremotely",
    "himalayas",
    "jobicy",
)
MARKETPLACE_SOURCES = ("upwork", "freelancer", "peopleperhour", "guru")
DISCOVERY_SOURCES = (
    "serpapi_freelance",
    "serpapi_jobs",
    "serpapi_companies",
    "serpapi_maps",
)

# Commercial product allowlists. Remotive and We Work Remotely stay registered for
# local demos but are excluded from paid plans until written commercial permission exists.
# Himalayas and Jobicy publish free public APIs intended for job-board integrations.
# SerpAPI discovery is Pro-only because each search consumes paid API credits.
COMMERCIAL_FREE_SOURCES = ("remoteok", "arbeitnow", "himalayas", "jobicy")
COMMERCIAL_PRO_SOURCES = COMMERCIAL_FREE_SOURCES + (
    "upwork",
    "freelancer",
    "linkedin_browser",
    "upwork_browser",
) + DISCOVERY_SOURCES
RESTRICTED_SOURCES = ("remotive", "weworkremotely", "peopleperhour", "guru")

SOURCE_ATTRIBUTION = {
    "remoteok": "Remote OK",
    "remotive": "Remotive",
    "arbeitnow": "Arbeitnow",
    "weworkremotely": "We Work Remotely",
    "himalayas": "Himalayas",
    "jobicy": "Jobicy",
    "upwork": "Upwork",
    "freelancer": "Freelancer.com",
    "peopleperhour": "PeoplePerHour",
    "guru": "Guru",
    "serpapi_freelance": "Google Search (via SerpAPI)",
    "serpapi_jobs": "Google Jobs (via SerpAPI)",
    "serpapi_companies": "Company careers (via SerpAPI)",
    "serpapi_maps": "Google Maps (via SerpAPI)",
    "linkedin_browser": "LinkedIn (Playwright)",
    "upwork_browser": "Upwork (Playwright)",
}
