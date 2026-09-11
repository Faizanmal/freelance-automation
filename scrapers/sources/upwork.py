from __future__ import annotations

from typing import Any

import httpx

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


class UpworkScraper:
    """Official Upwork GraphQL job search (requires OAuth access token)."""

    name = "upwork"

    def __init__(self, access_token: str, limit: int = 20, query: str = "python") -> None:
        self.access_token = access_token
        self.limit = limit
        self.query = query

    async def fetch_jobs(self) -> list[dict[str, Any]]:
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
                        "searchExpression": self.query,
                        "paging": {"offset": 0, "count": self.limit},
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()

        if payload.get("errors"):
            raise RuntimeError(payload["errors"])

        results = ((payload.get("data") or {}).get("marketplaceJobPostingsSearch") or {}).get("results") or []
        jobs: list[dict[str, Any]] = []
        for row in results:
            ciphertext = row.get("ciphertext")
            jobs.append(
                {
                    "source": self.name,
                    "external_id": str(row.get("id") or ciphertext),
                    "title": row.get("title") or "Untitled",
                    "company": "Upwork client",
                    "location": ((row.get("client") or {}).get("country")) or "Remote",
                    "description": row.get("description") or "",
                    "url": row.get("url")
                    or (f"https://www.upwork.com/jobs/{ciphertext}" if ciphertext else ""),
                    "posted_at": row.get("createdDateTime"),
                    "tags": [str(s.get("name")).lower() for s in (row.get("skills") or []) if s.get("name")],
                    "budget_min": (row.get("budget") or {}).get("amount"),
                    "budget_max": (row.get("budget") or {}).get("amount"),
                }
            )
            if len(jobs) >= self.limit:
                break
        return jobs
