from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


class RemoteOKScraper:
    """Public RemoteOK JSON API adapter."""

    name = "remoteok"
    api_url = "https://remoteok.com/api"

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit

    async def fetch_jobs(self, tags: list[str] | None = None) -> list[dict[str, Any]]:
        headers = {"User-Agent": "FreelanceIntelligence/0.1"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.api_url)
            response.raise_for_status()
            payload = response.json()

        wanted = {tag.lower() for tag in (tags or [])}
        jobs: list[dict[str, Any]] = []
        for row in payload:
            if not isinstance(row, dict) or "id" not in row:
                continue
            job_tags = [str(tag).lower() for tag in (row.get("tags") or [])]
            if wanted and not wanted.intersection(job_tags):
                continue
            epoch = row.get("epoch")
            posted_at = (
                datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
                if isinstance(epoch, (int, float))
                else row.get("date")
            )
            jobs.append(
                {
                    "source": self.name,
                    "external_id": str(row["id"]),
                    "title": row.get("position") or "Untitled",
                    "company": row.get("company"),
                    "location": row.get("location") or "Remote",
                    "description": row.get("description") or "",
                    "url": row.get("url") or f"https://remoteok.com/remote-jobs/{row['id']}",
                    "posted_at": posted_at,
                    "tags": job_tags,
                    "budget_min": row.get("salary_min"),
                    "budget_max": row.get("salary_max"),
                }
            )
            if len(jobs) >= self.limit:
                break
        return jobs
