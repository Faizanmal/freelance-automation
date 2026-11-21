"""Unit tests for Phase 07 ranking profile, explanations, and pipeline."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.application.services.ranking.pipeline import RankingPipeline
from backend.application.services.ranking.profile import MatchProfileBuilder
from database.models.job import JobRecord
from database.models.preference import UserPreferences


def _prefs(**overrides) -> UserPreferences:
    base = dict(
        user_id="u1",
        skills=["python", "fastapi"],
        keywords=["remote"],
        exclude_keywords=["crypto"],
        sources=[],
        match_threshold=0.35,
        freelance_focus=True,
        notification_channels=[],
    )
    base.update(overrides)
    return UserPreferences(**base)


def _job(**overrides) -> JobRecord:
    base = dict(
        id=1,
        source_name="ats_direct",
        source_id="j1",
        canonical_id="c-j1",
        title="Python FastAPI contractor",
        description="Remote freelance FastAPI work. $80/hr.",
        url="https://example.com/j1",
        company="Acme",
        location="Remote",
        tags=["python", "fastapi"],
        budget_min=70,
        budget_max=90,
        posted_at="2 hours ago",
        enrichment={"skills": ["python", "fastapi"], "engagement_type": "contract"},
        seniority="mid",
    )
    base.update(overrides)
    return JobRecord(**base)


class RankingPipelineTests(unittest.TestCase):
    def test_profile_distinguishes_hard_soft_unknown(self) -> None:
        profile = MatchProfileBuilder().build(
            _prefs(experience_level="any", location=None, timezone=None),
            learning_enabled=False,
        )
        hard_keys = {f.key for f in profile.hard}
        soft_keys = {f.key for f in profile.soft}
        unknown_keys = {f.key for f in profile.unknowns}
        self.assertIn("exclude_keywords", hard_keys)
        self.assertIn("skills", soft_keys)
        self.assertIn("experience_level", unknown_keys)
        self.assertFalse(profile.to_dict()["sensitive_traits_inferred"])

    def test_cold_start_widens_threshold(self) -> None:
        profile = MatchProfileBuilder().build(
            _prefs(skills=[], keywords=[], match_threshold=0.35),
            learning_enabled=False,
        )
        self.assertTrue(profile.cold_start)
        self.assertEqual(profile.match_threshold, 0.25)

    def test_learning_weights_require_flag(self) -> None:
        profile = MatchProfileBuilder().build(
            _prefs(),
            skill_weights={"python": 0.1},
            learning_enabled=False,
        )
        self.assertEqual(profile.skill_weights, {})
        enabled = MatchProfileBuilder().build(
            _prefs(),
            skill_weights={"python": 0.1},
            learning_enabled=True,
        )
        self.assertIn("python", enabled.skill_weights)

    def test_pipeline_default_weighted(self) -> None:
        with patch.dict(os.environ, {"MATCH_PIPELINE": "weighted_v1", "MATCH_SEMANTIC_RETRIEVAL": "0"}):
            ranked = RankingPipeline().rank(
                [_job()],
                _prefs(match_threshold=0.2),
                learning_enabled=False,
            )
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].score_version, "weighted_v1")
        self.assertIsNone(ranked[0].explanation.to_dict()["calibrated_probability"])

    def test_hybrid_failure_falls_back(self) -> None:
        pipeline = RankingPipeline()

        def boom(*_a, **_k):
            raise RuntimeError("semantic boom")

        with patch.object(pipeline, "_rank_hybrid", side_effect=boom):
            ranked = pipeline.rank(
                [_job()],
                _prefs(match_threshold=0.2),
                learning_enabled=False,
                pipeline_mode="hybrid_v1",
                semantic_enabled=True,
            )
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].score_version, "weighted_v1")
        self.assertEqual(ranked[0].retrieval_path, "keyword_fallback")

    def test_duplicate_collapse(self) -> None:
        jobs = [
            _job(id=1, canonical_id="same", source_id="j1", title="A", url="https://example.com/a"),
            _job(
                id=2,
                canonical_id="same",
                title="A copy",
                url="https://example.com/a-copy",
                source_id="j2",
            ),
        ]
        ranked = RankingPipeline().rank(
            jobs,
            _prefs(match_threshold=0.2),
            learning_enabled=False,
            pipeline_mode="weighted_v1",
        )
        self.assertEqual(len(ranked), 1)


if __name__ == "__main__":
    unittest.main()
