"""P1: scrape verification gate + sync fallback when Celery is unavailable."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.jobs import ScrapeRequest, scrape_jobs

from fastapi import HTTPException


class ScrapeGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_unverified_user_cannot_scrape(self) -> None:
        user = SimpleNamespace(
            is_verified=False,
            plan="free",
            subscription_status="inactive",
        )
        with self.assertRaises(HTTPException) as ctx:
            await scrape_jobs(
                ScrapeRequest(sources=["remoteok"], limit=5),
                session=AsyncMock(),
                current_user=user,  # type: ignore[arg-type]
            )
        self.assertEqual(ctx.exception.status_code, 403)
        detail = ctx.exception.detail
        assert isinstance(detail, dict)
        self.assertEqual(detail["code"], "email_verification_required")

    async def test_verified_scrape_returns_sync_stats(self) -> None:
        user = SimpleNamespace(
            is_verified=True,
            plan="free",
            subscription_status="inactive",
        )
        summary = {
            "sources": {
                "remoteok": {
                    "fetched": 3,
                    "ingested": 2,
                    "merged": 0,
                    "linked": 0,
                    "skipped": 1,
                }
            },
            "total_fetched": 3,
            "total_ingested": 2,
            "total_merged": 0,
            "total_skipped": 1,
            "alerts_sent": 0,
            "new_job_ids": [1, 2],
        }
        mock_service = MagicMock()
        mock_service.run = AsyncMock(return_value=summary)

        with patch("app.api.v1.jobs.ScrapeService", return_value=mock_service):
            result = await scrape_jobs(
                ScrapeRequest(sources=["remoteok"], limit=5, background=False),
                session=AsyncMock(),
                current_user=user,  # type: ignore[arg-type]
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["total_fetched"], 3)
        self.assertEqual(result["total_ingested"], 2)
        self.assertIsNone(result["task_id"])
        mock_service.run.assert_awaited_once()

    async def test_background_falls_back_to_sync_when_celery_unavailable(self) -> None:
        user = SimpleNamespace(
            is_verified=True,
            plan="free",
            subscription_status="inactive",
        )
        summary = {
            "sources": {},
            "total_fetched": 1,
            "total_ingested": 1,
            "total_merged": 0,
            "total_skipped": 0,
            "alerts_sent": 0,
            "new_job_ids": [9],
        }
        mock_service = MagicMock()
        mock_service.run = AsyncMock(return_value=summary)

        with (
            patch("app.api.v1.jobs.ScrapeService", return_value=mock_service),
            patch(
                "workers.availability.celery_workers_online",
                return_value=False,
            ),
        ):
            result = await scrape_jobs(
                ScrapeRequest(sources=["remoteok"], limit=5, background=True),
                session=AsyncMock(),
                current_user=user,  # type: ignore[arg-type]
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["total_fetched"], 1)
        mock_service.run.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
