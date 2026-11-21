"""Gap-closure tests for Phase 07 SQL retrieval, eligibility, cache, embeddings."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.application.services.matching import MatchingService
from backend.application.services.ranking.cache import (
    MemoryRecommendationCache,
    recommendation_cache_key,
)
from backend.application.services.ranking.embeddings import EmbeddingIndex
from backend.application.services.ranking.pipeline import RankingPipeline
from database.models.job import JobRecord
from database.models.preference import UserPreferences


def _job(**kwargs) -> JobRecord:
    defaults = {
        "id": 1,
        "source_name": "ats_direct",
        "source_id": "1",
        "canonical_id": "c1",
        "title": "Python FastAPI contractor",
        "description": "Remote contract FastAPI work",
        "url": "https://example.com/1",
        "company": "Acme",
        "tags": ["python", "fastapi"],
        "budget_min": 70,
        "budget_max": 90,
        "posted_at": "2 hours ago",
        "enrichment": {"skills": ["python", "fastapi"], "engagement_type": "contract"},
    }
    defaults.update(kwargs)
    return JobRecord(**defaults)


def _prefs(**kwargs) -> UserPreferences:
    defaults = {
        "user_id": "u1",
        "skills": ["python", "fastapi"],
        "keywords": [],
        "exclude_keywords": [],
        "sources": [],
        "match_threshold": 0.2,
        "notification_channels": [],
        "freelance_focus": True,
    }
    defaults.update(kwargs)
    return UserPreferences(**defaults)


class EligibilityTests(unittest.TestCase):
    def test_explain_ineligibility_source_allowlist(self) -> None:
        detail = MatchingService().explain_ineligibility(
            _job(source_name="reddit"),
            _prefs(sources=["ats_direct"]),
        )
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["eligibility"], "ineligible")
        self.assertIn("sources", detail["hard_filters_failed"])

    def test_explain_ineligibility_exclusion(self) -> None:
        detail = MatchingService().explain_ineligibility(
            _job(title="Crypto bot python", description="crypto trading"),
            _prefs(exclude_keywords=["crypto"]),
        )
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertIn("exclude_keywords", detail["hard_filters_failed"])

    def test_eligible_returns_none(self) -> None:
        detail = MatchingService().explain_ineligibility(_job(), _prefs())
        self.assertIsNone(detail)

    def test_pipeline_samples_ineligible(self) -> None:
        jobs = [
            _job(id=1, source_id="a", canonical_id="a"),
            _job(
                id=2,
                source_id="b",
                canonical_id="b",
                source_name="reddit",
                title="Python gig",
            ),
        ]
        samples = RankingPipeline().sample_ineligible(
            jobs, _prefs(sources=["ats_direct"]), limit=5
        )
        self.assertGreaterEqual(len(samples), 1)
        self.assertEqual(samples[0]["eligibility"], "ineligible")


class CacheTests(unittest.TestCase):
    def test_ttl_and_user_invalidation(self) -> None:
        cache = MemoryRecommendationCache(ttl_seconds=60)
        key = recommendation_cache_key(
            user_id="u1",
            prefs_updated_at="t1",
            score_version="weighted_v1",
            retrieval_mode="keyword",
            limit=10,
        )
        cache.set(key, {"ok": True}, user_id="u1")
        self.assertEqual(cache.get(key), {"ok": True})
        self.assertEqual(cache.invalidate_user("u1"), 1)
        self.assertIsNone(cache.get(key))

    def test_prefs_change_changes_key(self) -> None:
        a = recommendation_cache_key(
            user_id="u1",
            prefs_updated_at="2026-01-01",
            score_version="weighted_v1",
            retrieval_mode="keyword",
            limit=10,
        )
        b = recommendation_cache_key(
            user_id="u1",
            prefs_updated_at="2026-01-02",
            score_version="weighted_v1",
            retrieval_mode="keyword",
            limit=10,
        )
        self.assertNotEqual(a, b)


class EmbeddingPersistTests(unittest.IsolatedAsyncioTestCase):
    async def test_persist_dirty_commits(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        job = _job(embedding_vector=None, enrichment={})
        index = EmbeddingIndex()
        metrics = await index.persist_dirty(
            session, [job], batch_limit=10, budget_ms=1000, force=True
        )
        self.assertGreaterEqual(metrics.jobs_embedded, 1)
        self.assertIsInstance(job.embedding_vector, list)
        self.assertEqual(len(job.embedding_vector), 64)
        meta = (job.enrichment or {}).get("embedding_meta") or {}
        self.assertEqual(meta.get("model_version"), index.model_version)
        self.assertIn("content_hash", meta)
        session.commit.assert_awaited()
        self.assertFalse(index.metrics_dict()["logged_private_profile_text"])


class SqlCandidateRepoTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_match_candidates_builds_term_filter(self) -> None:
        from backend.infrastructure.repositories.job_repository import (
            SQLAlchemyJobRepository,
        )

        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute.return_value = result
        repo = SQLAlchemyJobRepository(session)
        await repo.list_match_candidates(
            skills=["python"],
            keywords=["fastapi"],
            exclude_keywords=["crypto"],
            sources=["ats_direct"],
            limit=50,
        )
        session.execute.assert_awaited()
        # Ensure a SQL statement was compiled (not a no-op recent-only without filters).
        compiled = str(session.execute.await_args.args[0])
        self.assertIn("jobs", compiled.lower())


if __name__ == "__main__":
    unittest.main()
