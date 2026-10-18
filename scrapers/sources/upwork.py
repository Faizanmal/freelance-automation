from __future__ import annotations

from typing import Any

import httpx

from scrapers.core.api_scraper import BaseApiScraper

TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
GRAPHQL_URL = "https://api.upwork.com/graphql"

JOB_SEARCH_QUERY = """
query SearchJobs($searchExpression: String, $paging: PagingInput) {
  marketplaceJobPostingsSearch(searchExpression: $searchExpression, paging: $paging) {
    total
    results {
      id
      title
      description
      skills { name }
      budget { amount currency }
      createdDateTime
      client { id country }
      ciphertext
      url
    }
  }
}
"""


class UpworkScraper(BaseApiScraper):
    """Official Upwork GraphQL job search (requires OAuth access token)."""

    name = "upwork"

    def __init__(self, access_token: str, limit: int = 20) -> None:
        super().__init__(limit=limit)
        self.access_token = access_token
        self.payload: list[dict[str, Any]] = []

    async def search(self, query: str = "python", **kwargs: Any) -> None:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                GRAPHQL_URL,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": JOB_SEARCH_QUERY,
                    "variables": {
                        "searchExpression": query,
                        "paging": {"offset": 0, "count": self.limit},
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

        if data.get("errors"):
            raise RuntimeError(data["errors"])

        results = (
            (data.get("data") or {}).get("marketplaceJobPostingsSearch") or {}
        ).get("results") or []
        self.payload = results

    async def extract_jobs(self) -> list[dict[str, Any]]:
        return self.payload[: self.limit]

    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        ciphertext = raw_job.get("ciphertext")
        return {
            "source": self.name,
            "external_id": str(raw_job.get("id") or ciphertext),
            "title": raw_job.get("title") or "Untitled",
            "company": "Upwork client",
            "location": ((raw_job.get("client") or {}).get("country")) or "Remote",
            "description": raw_job.get("description") or "",
            "url": raw_job.get("url")
            or (f"https://www.upwork.com/jobs/{ciphertext}" if ciphertext else ""),
            "posted_at": raw_job.get("createdDateTime"),
            "tags": [
                str(s.get("name")).lower()
                for s in (raw_job.get("skills") or [])
                if s.get("name")
            ],
            "budget_min": (raw_job.get("budget") or {}).get("amount"),
            "budget_max": (raw_job.get("budget") or {}).get("amount"),
        }
