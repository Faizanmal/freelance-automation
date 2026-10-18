from __future__ import annotations

from typing import Any

import httpx


class RemotiveScraper:
    """Public Remotive remote jobs API adapter."""

    name = "remotive"
    api_url = "https://remotive.com/api/remote-jobs"

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit

    async def fetch_jobs(self, category: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": self.limit}
        if category:
            params["category"] = category
        headers = {"User-Agent": "FreelanceIntelligence/0.1"}
        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            response = await client.get(self.api_url, params=params)
            response.raise_for_status()
            payload = response.json()

        jobs: list[dict[str, Any]] = []
        for row in payload.get("jobs") or []:
            jobs.append(
                {
                    "source": self.name,
                    "external_id": str(row.get("id")),
                    "title": row.get("title") or "Untitled",
                    "company": row.get("company_name"),
                    "location": row.get("candidate_required_location") or "Remote",
                    "description": row.get("description") or "",
                    "url": row.get("url") or row.get("job_url") or "",
                    "posted_at": row.get("publication_date"),
                    "tags": [str(tag).lower() for tag in (row.get("tags") or [])],
                    "category": row.get("category"),
                }
            )
            if len(jobs) >= self.limit:
                break
        return jobs
