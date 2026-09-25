from __future__ import annotations

from typing import Any

import httpx

from scrapers.core.api_scraper import BaseApiScraper


class HimalayasScraper(BaseApiScraper):
    name = "himalayas"
    api_url = "https://himalayas.app/jobs/api"
    page_size = 20

    def __init__(self, limit: int = 50) -> None:
        super().__init__(limit=limit)
        self.payload: list[dict[str, Any]] = []

    async def search(self, query: str = "", **kwargs: Any) -> None:
        headers = {"User-Agent": "FreelanceIntelligence/0.4"}
        offset = 0
        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            while len(self.payload) < self.limit:
                page_limit = min(self.page_size, self.limit - len(self.payload))
                response = await client.get(
                    self.api_url, params={"offset": offset, "limit": page_limit}
                )
                response.raise_for_status()
                rows = (response.json().get("jobs") or [])
                if not rows:
                    break
                
                # If a query is provided, we might want to filter locally since the API might not support it
                if query:
                    filtered = []
                    for r in rows:
                        title = str(r.get("title") or "").lower()
                        desc = str(r.get("description") or "").lower()
                        if query.lower() in title or query.lower() in desc:
                            filtered.append(r)
                    rows = filtered

                self.payload.extend(rows)
                offset += len(rows)
                if len(rows) < page_limit:
                    break

    async def extract_jobs(self) -> list[dict[str, Any]]:
        return self.payload[:self.limit]

    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        guid = raw_job.get("guid") or raw_job.get("applicationLink") or raw_job.get("title")
        location = raw_job.get("locationRestrictions") or []
        if isinstance(location, list):
            location_label = ", ".join(str(item) for item in location) or "Remote"
        else:
            location_label = str(location) or "Remote"

        return {
            "source": self.name,
            "external_id": str(guid),
            "title": raw_job.get("title") or "Untitled",
            "company": raw_job.get("companyName"),
            "location": location_label,
            "description": raw_job.get("description") or raw_job.get("excerpt") or "",
            "url": raw_job.get("applicationLink") or raw_job.get("guid") or "",
            "posted_at": raw_job.get("pubDate"),
            "tags": [
                str(tag).lower()
                for tag in (
                    *(raw_job.get("categories") or []),
                    *(raw_job.get("parentCategories") or []),
                )
                if tag
            ],
        }
