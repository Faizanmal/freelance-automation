from __future__ import annotations

from typing import Any

import httpx


class HimalayasScraper:
    name = "himalayas"
    api_url = "https://himalayas.app/jobs/api"
    page_size = 20

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit

    async def fetch_jobs(self) -> list[dict[str, Any]]:
        headers = {"User-Agent": "FreelanceIntelligence/0.4"}
        jobs: list[dict[str, Any]] = []
        offset = 0
        async with httpx.AsyncClient(
            timeout=30.0, headers=headers, follow_redirects=True
        ) as client:
            while len(jobs) < self.limit:
                page_limit = min(self.page_size, self.limit - len(jobs))
                response = await client.get(
                    self.api_url, params={"offset": offset, "limit": page_limit}
                )
                response.raise_for_status()
                rows = (response.json().get("jobs") or [])
                if not rows:
                    break
                for row in rows:
                    guid = row.get("guid") or row.get("applicationLink") or row.get("title")
                    location = row.get("locationRestrictions") or []
                    if isinstance(location, list):
                        location_label = ", ".join(str(item) for item in location) or "Remote"
                    else:
                        location_label = str(location) or "Remote"
                    jobs.append(
                        {
                            "source": self.name,
                            "external_id": str(guid),
                            "title": row.get("title") or "Untitled",
                            "company": row.get("companyName"),
                            "location": location_label,
                            "description": row.get("description") or row.get("excerpt") or "",
                            "url": row.get("applicationLink") or row.get("guid") or "",
                            "posted_at": row.get("pubDate"),
                            "tags": [
                                str(tag).lower()
                                for tag in (
                                    *(row.get("categories") or []),
                                    *(row.get("parentCategories") or []),
                                )
                                if tag
                            ],
                        }
                    )
                    if len(jobs) >= self.limit:
                        break
                offset += len(rows)
                if len(rows) < page_limit:
                    break
        return jobs
