from __future__ import annotations

from typing import Any

import httpx

from scrapers.core.api_scraper import BaseApiScraper


class FreelancerScraper(BaseApiScraper):
    """Official Freelancer.com active projects search."""

    name = "freelancer"
    api_url = "https://www.freelancer.com/api/projects/0.1/projects/active/"

    def __init__(self, oauth_token: str, limit: int = 20) -> None:
        super().__init__(limit=limit)
        self.oauth_token = oauth_token
        self.payload: list[dict[str, Any]] = []

    async def search(self, query: str = "python", **kwargs: Any) -> None:
        headers = {
            "Freelancer-OAuth-V1": self.oauth_token,
            "User-Agent": "FreelanceIntelligence/0.3",
            "Accept": "application/json",
        }
        params = {
            "query": query,
            "limit": self.limit,
            "offset": 0,
            "full_description": "true",
            "job_details": "true",
        }
        async with httpx.AsyncClient(
            timeout=45.0, headers=headers, follow_redirects=True
        ) as client:
            response = await client.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()

        self.payload = ((data.get("result") or {}).get("projects")) or []

    async def extract_jobs(self) -> list[dict[str, Any]]:
        return self.payload[: self.limit]

    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        project_id = raw_job.get("id")
        seo_url = raw_job.get("seo_url")
        budget = raw_job.get("budget") or {}
        return {
            "source": self.name,
            "external_id": str(project_id),
            "title": raw_job.get("title") or "Untitled",
            "company": "Freelancer.com client",
            "location": "Remote",
            "description": raw_job.get("description") or "",
            "url": (
                f"https://www.freelancer.com/projects/{seo_url}"
                if seo_url
                else f"https://www.freelancer.com/projects/{project_id}"
            ),
            "posted_at": raw_job.get("time_submitted"),
            "tags": [
                str(job.get("name")).lower()
                for job in (raw_job.get("jobs") or [])
                if isinstance(job, dict) and job.get("name")
            ],
            "budget_min": budget.get("minimum"),
            "budget_max": budget.get("maximum"),
        }
