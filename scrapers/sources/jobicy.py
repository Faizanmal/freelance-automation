from __future__ import annotations

from typing import Any

import httpx


class JobicyScraper:
    name = "jobicy"
    api_url = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit

    async def fetch_jobs(self) -> list[dict[str, Any]]:
        headers = {"User-Agent": "FreelanceIntelligence/0.4"}
        params = {"count": min(max(self.limit, 1), 100)}
        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            response = await client.get(self.api_url, params=params)
            response.raise_for_status()
            payload = response.json()

        jobs: list[dict[str, Any]] = []
        for row in payload.get("jobs") or []:
            industry = row.get("jobIndustry") or []
            if not isinstance(industry, list):
                industry = [industry] if industry else []
            jobs.append(
                {
                    "source": self.name,
                    "external_id": str(row.get("id") or row.get("jobSlug") or row.get("url")),
                    "title": row.get("jobTitle") or "Untitled",
                    "company": row.get("companyName"),
                    "location": row.get("jobGeo") or "Remote",
                    "description": row.get("jobDescription") or row.get("jobExcerpt") or "",
                    "url": row.get("url") or "",
                    "posted_at": row.get("pubDate"),
                    "tags": [str(tag).lower() for tag in industry if tag],
                }
            )
            if len(jobs) >= self.limit:
                break
        return jobs
