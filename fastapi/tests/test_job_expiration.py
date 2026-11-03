"""Tests for lead expiration, TTL staleness detection, and dead link handling."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from backend.application.services.job_expiration import JobExpirationService
from backend.application.services.lead_findings import LeadFindingsService
from backend.infrastructure.repositories.job_repository import SQLAlchemyJobRepository
from database.models.job import JobRecord


def _make_job(
    job_id: int,
    source_name: str = "serpapi_freelance",
    posted_days_ago: int = 1,
    is_expired: bool = False,
) -> JobRecord:
    posted = (datetime.now(UTC) - timedelta(days=posted_days_ago)).isoformat()
    return JobRecord(
        id=job_id,
        source_name=source_name,
        source_id=f"src-{job_id}",
        canonical_id=f"canon-{job_id}",
        title=f"Engineer {job_id}",
        description="Looking for an engineer to build services",
        url=f"https://example.com/jobs/{job_id}",
        company="Acme Corp",
        posted_at=posted,
        is_expired=is_expired,
        tags=["python", "fastapi"],
    )


class JobExpirationTTLTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = JobExpirationService()

    def test_recent_job_is_not_stale(self) -> None:
        job = _make_job(1, source_name="serpapi_freelance", posted_days_ago=5)
        self.assertFalse(self.service.is_stale_by_ttl(job))

    def test_old_serpapi_job_is_stale(self) -> None:
        # Default TTL for serpapi is 30 days
        job = _make_job(2, source_name="serpapi_freelance", posted_days_ago=35)
        self.assertTrue(self.service.is_stale_by_ttl(job))

    def test_reddit_hiring_stale_after_14_days(self) -> None:
        recent_reddit = _make_job(3, source_name="reddit_hiring", posted_days_ago=10)
        self.assertFalse(self.service.is_stale_by_ttl(recent_reddit))

        old_reddit = _make_job(4, source_name="reddit_hiring", posted_days_ago=16)
        self.assertTrue(self.service.is_stale_by_ttl(old_reddit))

    def test_invalid_or_missing_date_defaults_to_not_stale(self) -> None:
        job = _make_job(5)
        job.posted_at = "invalid-date-string"
        job.created_at = None
        self.assertFalse(self.service.is_stale_by_ttl(job))


class JobExpirationUrlHealthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = JobExpirationService()

    async def test_invalid_url_returns_dead(self) -> None:
        res = await self.service.check_url_health("ftp://invalid.com")
        self.assertFalse(res["is_alive"])
        self.assertEqual(res["reason"], "invalid_url")

    async def test_200_ok_returns_alive(self) -> None:
        mock_resp = MagicMock(status_code=200)
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_resp):
            res = await self.service.check_url_health("https://example.com/job/1")
            self.assertTrue(res["is_alive"])
            self.assertEqual(res["status_code"], 200)

    async def test_404_not_found_returns_dead(self) -> None:
        mock_resp = MagicMock(status_code=404)
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_resp):
            res = await self.service.check_url_health("https://example.com/job/404")
            self.assertFalse(res["is_alive"])
            self.assertEqual(res["reason"], "not_found")
            self.assertEqual(res["status_code"], 404)

    async def test_timeout_returns_dead(self) -> None:
        with patch(
            "httpx.AsyncClient.head",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Read timed out"),
        ):
            res = await self.service.check_url_health("https://example.com/slow")
            self.assertFalse(res["is_alive"])
            self.assertEqual(res["reason"], "timeout")


class JobExpirationRepositoryAndFindingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_expired_marks_job_and_creates_skip(self) -> None:
        job = _make_job(10)
        session = AsyncMock()
        session.get.return_value = job
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        service = JobExpirationService(session=session)
        updated = await service.report_expired(job_id=10, user_id="user-42", reason="dead_link")

        self.assertIsNotNone(updated)
        self.assertTrue(job.is_expired)
        self.assertEqual(job.expired_reason, "dead_link")
        self.assertIsNotNone(job.expired_at)

        # Added user lead action with status="skip"
        self.assertTrue(session.add.called)
        self.assertTrue(session.commit.called)

    def test_lead_findings_excludes_expired_jobs(self) -> None:
        jobs = [
            _make_job(1, is_expired=False),
            _make_job(2, is_expired=True),
        ]
        prefs = SimpleNamespace(
            keywords=["python"],
            exclude_keywords=[],
            min_budget=None,
            max_budget=None,
            min_hourly_rate=None,
            match_threshold=0.1,
            sources=[],
        )
        matcher = MagicMock()
        matcher.rank_jobs.return_value = [
            MagicMock(
                job=jobs[0],
                score=0.9,
                matched_keywords=["python"],
                reasons=["kw"],
                freshness_score=0.8,
                client_quality_score=0.7,
                red_flags=[],
            )
        ]
        service = LeadFindingsService(matcher=matcher)
        payload = service.build(
            jobs,  # type: ignore[arg-type]
            prefs,  # type: ignore[arg-type]
            limit=10,
            freelance_focus=False,
            include_expired=False,
        )

        # Rank jobs should only receive non-expired job
        passed_jobs = matcher.rank_jobs.call_args[0][0]
        self.assertEqual(len(passed_jobs), 1)
        self.assertEqual(passed_jobs[0].id, 1)


if __name__ == "__main__":
    unittest.main()
