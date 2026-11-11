"""Zero-cost direct Applicant Tracking System (ATS) ingestion.

Ingests contract, freelance, and remote opportunities directly from public,
unauthenticated JSON endpoints provided by major ATS platforms:
- Greenhouse: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
- Lever: https://api.lever.co/v0/postings/{company}?mode=json
- Ashby: https://api.ashbyhq.com/posting-api/job-board/{organization}
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.application.services.duplicate_detection import JobCandidate


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")

DEFAULT_GREENHOUSE_BOARDS = ("canonical", "gitlab", "automattic", "wikimedia")
DEFAULT_LEVER_COMPANIES = ("buffer", "hotjar", "zapier", "consensys")
DEFAULT_ASHBY_ORGS = ("sentry", "retool", "postman")

CONTRACT_KEYWORDS = (
    "contract",
    "contractor",
    "freelance",
    "freelancer",
    "consultant",
    "part-time",
    "part time",
    "temp",
    "temporary",
)


def _matches_query_or_contract(
    title: str, description: str, tags: list[str], query: str | None
) -> bool:
    """Check if posting matches specific search query or general contractor signals."""
    haystack = f"{title} {' '.join(tags)} {description[:500]}".lower()
    if query:
        q = query.strip().lower()
        if q in haystack:
            return True
    return any(ck in haystack for ck in CONTRACT_KEYWORDS)


def _safe_iso_from_epoch(value: int | float | None) -> str | None:
    if not value:
        return None
    try:
        # Lever gives epoch in milliseconds
        if value > 1e11:
            value = value / 1000.0
        return datetime.fromtimestamp(value, tz=UTC).isoformat()
    except (ValueError, OSError):
        return None


class GreenhouseSource:
    """Fetch jobs directly from Greenhouse public job board APIs."""

    name = "greenhouse"

    def __init__(self, boards: tuple[str, ...] = DEFAULT_GREENHOUSE_BOARDS) -> None:
        self.boards = boards

    async def fetch(
        self, *, limit: int = 50, query: str | None = None
    ) -> list[JobCandidate]:
        headers = {"User-Agent": "FreelanceIntelligence/1.0 (+https://freelance-intel.internal)"}
        jobs: list[JobCandidate] = []

        boards_to_query = self.boards
        if query and query.strip().lower() in self.boards:
            boards_to_query = (query.strip().lower(),)

        async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
            for board in boards_to_query:
                url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                except (httpx.RequestError, ValueError):
                    continue

                for item in data.get("jobs") or []:
                    if len(jobs) >= limit:
                        break
                    title = str(item.get("title") or "Untitled")
                    content_raw = str(item.get("content") or "")
                    description = strip_html(content_raw)
                    location_dict = item.get("location") or {}
                    location = (
                        location_dict.get("name")
                        if isinstance(location_dict, dict)
                        else "Remote"
                    ) or "Remote"

                    departments = [
                        str(d.get("name", "")).strip().lower()
                        for d in (item.get("departments") or [])
                        if isinstance(d, dict) and d.get("name")
                    ]
                    tags = [t for t in departments if t]

                    if not _matches_query_or_contract(title, description, tags, query):
                        continue

                    job_id = str(item.get("id"))
                    job_url = str(
                        item.get("absolute_url")
                        or f"https://boards.greenhouse.io/{board}/jobs/{job_id}"
                    )
                    company_name = board.replace("-", " ").title()

                    jobs.append(
                        JobCandidate(
                            source_name=self.name,
                            source_id=f"{board}-{job_id}",
                            title=title,
                            description=description[:2500],
                            url=job_url,
                            company=company_name,
                            budget_min=None,
                            budget_max=None,
                            posted_at=item.get("updated_at"),
                            metadata={
                                "location": location,
                                "tags": tags,
                                "ats": "greenhouse",
                                "board": board,
                            },
                        )
                    )

                if len(jobs) >= limit:
                    break

        return jobs


class LeverSource:
    """Fetch jobs directly from Lever public job postings APIs."""

    name = "lever"

    def __init__(self, companies: tuple[str, ...] = DEFAULT_LEVER_COMPANIES) -> None:
        self.companies = companies

    async def fetch(
        self, *, limit: int = 50, query: str | None = None
    ) -> list[JobCandidate]:
        headers = {"User-Agent": "FreelanceIntelligence/1.0 (+https://freelance-intel.internal)"}
        jobs: list[JobCandidate] = []

        target_companies = self.companies
        if query and query.strip().lower() in self.companies:
            target_companies = (query.strip().lower(),)

        async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
            for company in target_companies:
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                except (httpx.RequestError, ValueError):
                    continue

                if not isinstance(data, list):
                    continue

                for item in data:
                    if len(jobs) >= limit:
                        break
                    title = str(item.get("text") or "Untitled")
                    desc = str(
                        item.get("descriptionPlain")
                        or strip_html(item.get("description") or "")
                    )
                    categories = item.get("categories") or {}
                    commitment = str(categories.get("commitment") or "")
                    department = str(categories.get("department") or "")
                    team = str(categories.get("team") or "")
                    location = str(categories.get("location") or "Remote")

                    tags = [
                        t.lower()
                        for t in (commitment, department, team)
                        if t and t.lower() != "none"
                    ]

                    if not _matches_query_or_contract(title, desc, tags, query):
                        continue

                    job_id = str(item.get("id"))
                    job_url = str(
                        item.get("hostedUrl")
                        or item.get("applyUrl")
                        or f"https://jobs.lever.co/{company}/{job_id}"
                    )
                    company_name = company.replace("-", " ").title()

                    jobs.append(
                        JobCandidate(
                            source_name=self.name,
                            source_id=f"{company}-{job_id}",
                            title=title,
                            description=desc[:2500],
                            url=job_url,
                            company=company_name,
                            budget_min=None,
                            budget_max=None,
                            posted_at=_safe_iso_from_epoch(item.get("createdAt")),
                            metadata={
                                "location": location,
                                "tags": tags,
                                "ats": "lever",
                                "company": company,
                                "commitment": commitment,
                            },
                        )
                    )

                if len(jobs) >= limit:
                    break

        return jobs


class AshbySource:
    """Fetch jobs directly from Ashby public job board APIs."""

    name = "ashby"

    def __init__(self, organizations: tuple[str, ...] = DEFAULT_ASHBY_ORGS) -> None:
        self.organizations = organizations

    async def fetch(
        self, *, limit: int = 50, query: str | None = None
    ) -> list[JobCandidate]:
        headers = {"User-Agent": "FreelanceIntelligence/1.0 (+https://freelance-intel.internal)"}
        jobs: list[JobCandidate] = []

        target_orgs = self.organizations
        if query and query.strip().lower() in self.organizations:
            target_orgs = (query.strip().lower(),)

        async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
            for org in target_orgs:
                url = f"https://api.ashbyhq.com/posting-api/job-board/{org}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                except (httpx.RequestError, ValueError):
                    continue

                for item in data.get("jobs") or []:
                    if len(jobs) >= limit:
                        break
                    title = str(item.get("title") or "Untitled")
                    desc = str(
                        strip_html(item.get("descriptionHtml") or "")
                        or item.get("title")
                        or ""
                    )
                    emp_type = str(item.get("employmentType") or "")
                    department = str(item.get("department") or "")
                    location = str(item.get("location") or "Remote")

                    tags = [
                        t.lower()
                        for t in (emp_type, department)
                        if t and t.lower() != "none"
                    ]

                    if not _matches_query_or_contract(title, desc, tags, query):
                        continue

                    job_id = str(item.get("id"))
                    job_url = str(
                        item.get("jobUrl")
                        or f"https://jobs.ashbyhq.com/{org}/{job_id}"
                    )
                    company_name = org.replace("-", " ").title()

                    jobs.append(
                        JobCandidate(
                            source_name=self.name,
                            source_id=f"{org}-{job_id}",
                            title=title,
                            description=desc[:2500],
                            url=job_url,
                            company=company_name,
                            budget_min=None,
                            budget_max=None,
                            posted_at=item.get("publishedAt"),
                            metadata={
                                "location": location,
                                "tags": tags,
                                "ats": "ashby",
                                "organization": org,
                                "employment_type": emp_type,
                            },
                        )
                    )

                if len(jobs) >= limit:
                    break

        return jobs


class DirectATSSource:
    """Unified aggregator querying Greenhouse, Lever, and Ashby boards."""

    name = "ats_direct"

    def __init__(self) -> None:
        self.greenhouse = GreenhouseSource()
        self.lever = LeverSource()
        self.ashby = AshbySource()

    async def fetch(
        self, *, limit: int = 50, query: str | None = None
    ) -> list[JobCandidate]:
        per_source = max(1, limit // 3)
        gh_jobs = await self.greenhouse.fetch(limit=per_source, query=query)
        lev_jobs = await self.lever.fetch(limit=per_source, query=query)
        ash_jobs = await self.ashby.fetch(limit=per_source, query=query)

        combined = gh_jobs + lev_jobs + ash_jobs
        # Mark source_name as ats_direct for unified attribution while keeping original metadata
        for job in combined:
            job.metadata["underlying_source"] = job.source_name
            job.source_name = self.name
        return combined[:limit]
