from __future__ import annotations

from typing import Any

import httpx

from scrapers.core.api_scraper import BaseApiScraper


class ArbeitnowScraper(BaseApiScraper):
    name = "arbeitnow"
    api_url = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, limit: int = 50) -> None:
        super().__init__(limit=limit)
        self.payload: list[dict[str, Any]] = []

    async def search(self, query: str = "", **kwargs: Any) -> None:
        headers = {"User-Agent": "FreelanceIntelligence/0.2"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.api_url)
            response.raise_for_status()
            data = response.json().get("data") or []
            
            if query:
                filtered = []
                for r in data:
                    title = str(r.get("title") or "").lower()
                    desc = str(r.get("description") or "").lower()
                    if query.lower() in title or query.lower() in desc:
                        filtered.append(r)
                data = filtered

            self.payload = data

    async def extract_jobs(self) -> list[dict[str, Any]]:
        return self.payload[:self.limit]

    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        slug = raw_job.get("slug") or raw_job.get("url") or raw_job.get("title")
        return {
            "source": self.name,
            "external_id": str(slug),
            "title": raw_job.get("title") or "Untitled",
            "company": raw_job.get("company_name"),
            "location": raw_job.get("location") or "Remote",
            "description": raw_job.get("description") or "",
            "url": raw_job.get("url") or f"https://www.arbeitnow.com/view/{slug}",
            "posted_at": raw_job.get("created_at"),
            "tags": [str(tag).lower() for tag in (raw_job.get("tags") or [])],
        }
