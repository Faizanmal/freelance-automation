from __future__ import annotations

from typing import Any

import httpx

from scrapers.core.api_scraper import BaseApiScraper


class JobicyScraper(BaseApiScraper):
    name = "jobicy"
    api_url = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, limit: int = 50) -> None:
        super().__init__(limit=limit)
        self.payload: list[dict[str, Any]] = []

    async def search(self, query: str = "", **kwargs: Any) -> None:
        headers = {"User-Agent": "FreelanceIntelligence/0.4"}
        params = {"count": min(max(self.limit, 1), 100)}
        if kwargs.get("tag"):
            params["tag"] = kwargs["tag"]

        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            response = await client.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json().get("jobs") or []

            if query:
                filtered = []
                for r in data:
                    title = str(r.get("jobTitle") or "").lower()
                    desc = str(
                        r.get("jobDescription") or r.get("jobExcerpt") or ""
                    ).lower()
                    if query.lower() in title or query.lower() in desc:
                        filtered.append(r)
                data = filtered

            self.payload = data

    async def extract_jobs(self) -> list[dict[str, Any]]:
        return self.payload[: self.limit]

    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        industry = raw_job.get("jobIndustry") or []
        if not isinstance(industry, list):
            industry = [industry] if industry else []
        return {
            "source": self.name,
            "external_id": str(
                raw_job.get("id") or raw_job.get("jobSlug") or raw_job.get("url")
            ),
            "title": raw_job.get("jobTitle") or "Untitled",
            "company": raw_job.get("companyName"),
            "location": raw_job.get("jobGeo") or "Remote",
            "description": raw_job.get("jobDescription")
            or raw_job.get("jobExcerpt")
            or "",
            "url": raw_job.get("url") or "",
            "posted_at": raw_job.get("pubDate"),
            "tags": [str(tag).lower() for tag in industry if tag],
        }
