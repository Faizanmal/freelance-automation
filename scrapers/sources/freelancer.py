from __future__ import annotations

from typing import Any

import httpx


class FreelancerScraper:
    """Official Freelancer.com active projects search."""

    name = "freelancer"
    api_url = "https://www.freelancer.com/api/projects/0.1/projects/active/"

    def __init__(self, oauth_token: str, limit: int = 20, query: str = "python") -> None:
        self.oauth_token = oauth_token
        self.limit = limit
        self.query = query

    async def fetch_jobs(self) -> list[dict[str, Any]]:
        headers = {
            "Freelancer-OAuth-V1": self.oauth_token,
            "User-Agent": "FreelanceIntelligence/0.3",
            "Accept": "application/json",
        }
        params = {
            "query": self.query,
            "limit": self.limit,
            "offset": 0,
            "full_description": "true",
            "job_details": "true",
        }
        async with httpx.AsyncClient(timeout=45.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(self.api_url, params=params)
            response.raise_for_status()
            payload = response.json()

        projects = ((payload.get("result") or {}).get("projects")) or []
        jobs: list[dict[str, Any]] = []
        for project in projects:
            project_id = project.get("id")
            seo_url = project.get("seo_url")
            budget = project.get("budget") or {}
            jobs.append(
                {
                    "source": self.name,
                    "external_id": str(project_id),
                    "title": project.get("title") or "Untitled",
                    "company": "Freelancer.com client",
                    "location": "Remote",
                    "description": project.get("description") or "",
                    "url": (
                        f"https://www.freelancer.com/projects/{seo_url}"
                        if seo_url
                        else f"https://www.freelancer.com/projects/{project_id}"
                    ),
                    "posted_at": project.get("time_submitted"),
                    "tags": [
                        str(job.get("name")).lower()
                        for job in (project.get("jobs") or [])
                        if isinstance(job, dict) and job.get("name")
                    ],
                    "budget_min": budget.get("minimum"),
                    "budget_max": budget.get("maximum"),
                }
            )
            if len(jobs) >= self.limit:
                break
        return jobs
