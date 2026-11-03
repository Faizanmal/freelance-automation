from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.application.services.duplicate_detection import JobCandidate
from backend.application.services.scrape_service import ScrapeService


class ScrapeCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_redis_cache_hit_skips_fetch(self) -> None:
        mock_session = AsyncMock()
        service = ScrapeService(mock_session)

        candidate = JobCandidate(
            source_name="serpapi_freelance",
            source_id="12345",
            title="Senior React Contractor",
            description="3 month contract building design systems.",
            url="https://example.com/job/12345",
            company="Acme Corp",
            posted_at="2026-11-01T12:00:00Z",
            metadata={"location": "Remote"},
        )

        with patch.object(
            service, "_get_cached_candidates", new_callable=AsyncMock
        ) as mock_get_cache:
            mock_get_cache.return_value = [candidate]

            mock_source = MagicMock()
            mock_source.fetch = AsyncMock()

            with patch.dict(
                "backend.application.services.scrape_service.SOURCE_REGISTRY",
                {"serpapi_freelance": lambda: mock_source},
            ):
                with patch.object(
                    service.ingestion, "ingest", new_callable=AsyncMock
                ) as mock_ingest:
                    mock_ingest.return_value = {"action": "ingested", "job_id": 99}

                    result = await service.run(
                        sources=["serpapi_freelance"], limit=10, query="react"
                    )

                    # Live fetch should NOT be called because it was a cache hit!
                    mock_source.fetch.assert_not_called()
                    self.assertEqual(result["total_ingested"], 1)
                    self.assertEqual(result["sources"]["serpapi_freelance"]["fetched"], 1)

    async def test_redis_cache_miss_fetches_and_sets_cache(self) -> None:
        mock_session = AsyncMock()
        service = ScrapeService(mock_session)

        candidate = JobCandidate(
            source_name="serpapi_freelance",
            source_id="67890",
            title="Python Cloud Engineer",
            description="FastAPI + AWS microservices contract.",
            url="https://example.com/job/67890",
            company="Tech Corp",
            posted_at="2026-11-01T12:00:00Z",
            metadata={"location": "Remote"},
        )

        with patch.object(
            service, "_get_cached_candidates", new_callable=AsyncMock
        ) as mock_get_cache:
            mock_get_cache.return_value = None  # Cache miss!

            with patch.object(
                service, "_set_cached_candidates", new_callable=AsyncMock
            ) as mock_set_cache:
                mock_source = MagicMock()
                mock_source.fetch = AsyncMock(return_value=[candidate])

                with patch.dict(
                    "backend.application.services.scrape_service.SOURCE_REGISTRY",
                    {"serpapi_freelance": lambda: mock_source},
                ):
                    with patch.object(
                        service.ingestion, "ingest", new_callable=AsyncMock
                    ) as mock_ingest:
                        mock_ingest.return_value = {"action": "ingested", "job_id": 100}

                        result = await service.run(
                            sources=["serpapi_freelance"], limit=10, query="python"
                        )

                        mock_source.fetch.assert_called_once()
                        mock_set_cache.assert_called_once()
                        self.assertEqual(result["total_ingested"], 1)

