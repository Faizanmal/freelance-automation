"""Remaining: DomainJobMatchService.batch_match with injected loaders."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from backend.application.services.job_match_service import DomainJobMatchService
from backend.domain.models import JobOpportunity, UserPreferences


class BatchMatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_match_without_loaders_returns_empty(self) -> None:
        service = DomainJobMatchService()
        self.assertEqual(await service.batch_match(["1"], "u1"), [])

    async def test_batch_match_scores_and_sorts(self) -> None:
        prefs = UserPreferences(
            user_id="u1",
            keywords=["python", "fastapi"],
            preferred_sources=[],
            min_budget=None,
        )
        jobs = [
            JobOpportunity(
                source="remoteok",
                external_id="1",
                title="Python FastAPI engineer",
                company="Acme",
                location="Remote",
                description="Need python fastapi expert",
                url="https://example.com/1",
                posted_at=datetime.now(UTC),
                metadata={"budget_max": 5000, "tags": ["python"]},
            ),
            JobOpportunity(
                source="remoteok",
                external_id="2",
                title="Gardener",
                company="Yard",
                location="Local",
                description="Mow lawns",
                url="https://example.com/2",
                posted_at=datetime.now(UTC),
                metadata={},
            ),
        ]

        async def get_jobs(_ids: list[str]):
            return jobs

        async def get_preferences(_user_id: str):
            return prefs

        service = DomainJobMatchService(
            get_jobs=get_jobs, get_preferences=get_preferences
        )
        matches = await service.batch_match(["1", "2"], "u1")
        self.assertEqual(len(matches), 1)
        self.assertIn(
            "python", " ".join(matches[0].score_result.matched_keywords).lower()
        )


if __name__ == "__main__":
    unittest.main()
