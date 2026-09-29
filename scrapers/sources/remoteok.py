from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from scrapers.core.api_scraper import BaseApiScraper


class RemoteOKScraper(BaseApiScraper):
    """Public RemoteOK JSON API adapter."""

    name = "remoteok"
    api_url = "https://remoteok.com/api"

    def __init__(self, limit: int = 50) -> None:
        super().__init__(limit=limit)
        self.payload: list[dict[str, Any]] = []
        self.tags: list[str] = []

    async def search(self, query: str = "", **kwargs: Any) -> None:
        if query:
            self.tags = [query]
        if kwargs.get("tags"):
            self.tags = kwargs["tags"]

        headers = {"User-Agent": "FreelanceIntelligence/0.1"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.api_url)
            response.raise_for_status()
            self.payload = response.json()

    async def extract_jobs(self) -> list[dict[str, Any]]:
        wanted = {tag.lower() for tag in self.tags}
        raw_jobs: list[dict[str, Any]] = []
        for row in self.payload:
            if not isinstance(row, dict) or "id" not in row:
                continue
            job_tags = [str(tag).lower() for tag in (row.get("tags") or [])]
            if wanted and not wanted.intersection(job_tags):
                continue
            raw_jobs.append(row)
            if len(raw_jobs) >= self.limit:
                break
        return raw_jobs

    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        epoch = raw_job.get("epoch")
        posted_at = (
            datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
            if isinstance(epoch, (int, float))
            else raw_job.get("date")
        )
        job_tags = [str(tag).lower() for tag in (raw_job.get("tags") or [])]
        return {
            "source": self.name,
            "external_id": str(raw_job["id"]),
            "title": raw_job.get("position") or "Untitled",
            "company": raw_job.get("company"),
            "location": raw_job.get("location") or "Remote",
            "description": raw_job.get("description") or "",
            "url": raw_job.get("url") or f"https://remoteok.com/remote-jobs/{raw_job['id']}",
            "posted_at": posted_at,
            "tags": job_tags,
            "budget_min": raw_job.get("salary_min"),
            "budget_max": raw_job.get("salary_max"),
        }
