from __future__ import annotations

from typing import Any

import httpx


class ArbeitnowScraper:
    name = "arbeitnow"
    api_url = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit

    async def fetch_jobs(self) -> list[dict[str, Any]]:
        headers = {"User-Agent": "FreelanceIntelligence/0.2"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.api_url)
            response.raise_for_status()
            payload = response.json()

        jobs: list[dict[str, Any]] = []
        for row in payload.get("data") or []:
            slug = row.get("slug") or row.get("url") or row.get("title")
            jobs.append(
                {
                    "source": self.name,
                    "external_id": str(slug),
                    "title": row.get("title") or "Untitled",
                    "company": row.get("company_name"),
                    "location": row.get("location") or "Remote",
                    "description": row.get("description") or "",
                    "url": row.get("url") or f"https://www.arbeitnow.com/view/{slug}",
                    "posted_at": row.get("created_at"),
                    "tags": [str(tag).lower() for tag in (row.get("tags") or [])],
                }
            )
            if len(jobs) >= self.limit:
                break
        return jobs
