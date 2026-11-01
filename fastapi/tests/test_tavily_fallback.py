"""Tavily primary + SerpAPI fallback for discovery hunters."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.integrations import serpapi_discovery


class TavilyFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_tavily_wins_when_it_returns_rows(self) -> None:
        tavily_rows = [
            {
                "source_id": "t1",
                "title": "Need FastAPI contractor",
                "description": "Looking for freelancer",
                "url": "https://example.com/hire",
                "company": "example.com",
                "tags": ["discovery", "tavily", "freelance"],
                "location": "Remote / web discovery",
                "metadata": {"provider": "tavily"},
            }
        ]
        with (
            patch(
                "app.integrations.tavily_discovery.tavily_configured",
                return_value=True,
            ),
            patch(
                "app.integrations.tavily_discovery.search_discovery",
                new=AsyncMock(return_value=tavily_rows),
            ) as tavily_search,
            patch(
                "app.integrations.serpapi_discovery._search_serpapi",
                new=AsyncMock(),
            ) as serpapi_search,
        ):
            rows = await serpapi_discovery.search_discovery(
                mode="freelance", limit=5
            )

        self.assertEqual(rows, tavily_rows)
        tavily_search.assert_awaited_once()
        serpapi_search.assert_not_awaited()

    async def test_empty_tavily_falls_back_to_serpapi(self) -> None:
        serpapi_rows = [
            {
                "source_id": "s1",
                "title": "SerpAPI hit",
                "description": "Need a contractor",
                "url": "https://example.com/serp",
                "company": "example.com",
                "tags": ["discovery", "serpapi", "freelance"],
                "location": "Remote / web discovery",
                "metadata": {"provider": "serpapi"},
            }
        ]
        with (
            patch(
                "app.integrations.tavily_discovery.tavily_configured",
                return_value=True,
            ),
            patch(
                "app.integrations.tavily_discovery.search_discovery",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "app.integrations.serpapi_discovery._search_serpapi",
                new=AsyncMock(return_value=serpapi_rows),
            ) as serpapi_search,
        ):
            rows = await serpapi_discovery.search_discovery(mode="jobs", limit=5)

        self.assertEqual(rows, serpapi_rows)
        serpapi_search.assert_awaited_once()

    async def test_tavily_error_falls_back_to_serpapi(self) -> None:
        serpapi_rows = [{"source_id": "s2", "title": "Fallback", "url": "https://x.test"}]
        with (
            patch(
                "app.integrations.tavily_discovery.tavily_configured",
                return_value=True,
            ),
            patch(
                "app.integrations.tavily_discovery.search_discovery",
                new=AsyncMock(side_effect=RuntimeError("tavily down")),
            ),
            patch(
                "app.integrations.serpapi_discovery._search_serpapi",
                new=AsyncMock(return_value=serpapi_rows),
            ),
        ):
            rows = await serpapi_discovery.search_discovery(
                mode="companies", limit=3
            )

        self.assertEqual(rows, serpapi_rows)

    async def test_maps_skips_tavily(self) -> None:
        maps_rows = [{"source_id": "m1", "title": "Outreach: Co", "url": "https://co.test"}]
        with (
            patch(
                "app.integrations.tavily_discovery.tavily_configured",
                return_value=True,
            ),
            patch(
                "app.integrations.tavily_discovery.search_discovery",
                new=AsyncMock(),
            ) as tavily_search,
            patch(
                "app.integrations.serpapi_discovery._search_serpapi",
                new=AsyncMock(return_value=maps_rows),
            ),
        ):
            rows = await serpapi_discovery.search_discovery(mode="maps", limit=5)

        self.assertEqual(rows, maps_rows)
        tavily_search.assert_not_awaited()

    async def test_tavily_maps_rows_from_api_payload(self) -> None:
        from app.integrations import tavily_discovery

        payload = {
            "results": [
                {
                    "title": "Looking for Python freelancer",
                    "url": "https://hire.example/python",
                    "content": "Need a contractor for FastAPI work this month.",
                    "score": 0.91,
                },
                {
                    "title": "How to become a freelancer course",
                    "url": "https://learn.example/course",
                    "content": "Tutorial for beginners",
                    "score": 0.4,
                },
            ]
        }
        with (
            patch("app.integrations.tavily_discovery.get_settings") as settings,
            patch(
                "app.integrations.tavily_discovery._post_json",
                new=AsyncMock(return_value=payload),
            ),
        ):
            settings.return_value.tavily_api_key = "tvly-test"
            settings.return_value.tavily_search_depth = "basic"
            settings.return_value.serpapi_freelance_query = "python freelancer"
            rows = await tavily_discovery.search_discovery(
                mode="freelance", limit=10
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metadata"]["provider"], "tavily")
        self.assertIn("tavily", rows[0]["tags"])


if __name__ == "__main__":
    unittest.main()
