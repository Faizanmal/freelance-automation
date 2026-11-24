"""Save/Skip lead actions filter findings and persist per user."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.application.services.lead_findings import LeadFindingsService
from backend.application.services.ranking.explanation import ScoreExplanation
from backend.application.services.ranking.pipeline import RankedMatch


def _job(job_id: int, title: str = "Role") -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        title=title,
        company="Acme",
        source_name="serpapi_freelance",
        # Unique hosts so hard domain-cap does not collapse fixtures.
        url=f"https://job-{job_id}.example.test/posting/{job_id}",
        description="Looking for a freelance python contractor for a short project",
        location="Remote",
        tags=["python", "freelance"],
        enrichment={},
        seniority=None,
        posted_at=None,
        budget_min=None,
        budget_max=None,
        is_expired=False,
    )


def _ranked(job: SimpleNamespace, score: float) -> RankedMatch:
    return RankedMatch(
        job=job,  # type: ignore[arg-type]
        score=score,
        fit_score=score,
        matched_keywords=["python"],
        reasons=["kw"],
        freshness_score=0.8,
        client_quality_score=0.7,
        red_flags=[],
        explanation=ScoreExplanation(score_version="weighted_v1", fit_score=score),
        score_version="weighted_v1",
        retrieval_path="sql",
    )


class LeadActionFilterTests(unittest.TestCase):
    def test_skipped_jobs_hidden_by_default(self) -> None:
        jobs = [_job(1, "Keep"), _job(2, "Skip me")]
        prefs = SimpleNamespace(
            keywords=["python", "freelance"],
            exclude_keywords=[],
            min_budget=None,
            max_budget=None,
            match_threshold=0.1,
            sources=[],
            freelance_focus=False,
        )
        pipeline = MagicMock()
        pipeline.rank.return_value = [
            _ranked(jobs[0], 0.9),
            _ranked(jobs[1], 0.85),
        ]
        service = LeadFindingsService(pipeline=pipeline)
        payload = service.build(
            jobs,  # type: ignore[arg-type]
            prefs,  # type: ignore[arg-type]
            limit=10,
            freelance_focus=False,
            skip_job_ids={2},
            saved_job_ids={1},
        )
        ids = [item["job_id"] for item in payload["items"]]
        self.assertIn(1, ids)
        self.assertNotIn(2, ids)
        self.assertEqual(payload["items"][0]["user_status"], "save")

    def test_pitched_and_won_status_and_boost(self) -> None:
        jobs = [_job(1, "Normal"), _job(2, "Saved"), _job(3, "Pitched")]
        prefs = SimpleNamespace(
            keywords=["python", "freelance"],
            exclude_keywords=[],
            min_budget=None,
            max_budget=None,
            match_threshold=0.1,
            sources=[],
            freelance_focus=False,
        )
        pipeline = MagicMock()
        # Higher pitched fit + action boost should keep it on top.
        pipeline.rank.return_value = [
            _ranked(jobs[0], 0.82),
            _ranked(jobs[1], 0.88),
            _ranked(jobs[2], 0.9),
        ]
        service = LeadFindingsService(pipeline=pipeline)
        lead_actions = {2: "save", 3: "pitched"}
        applications = {
            3: {
                "id": 101,
                "status": "submitted",
                "submitted_at": "2026-11-01T20:00:00Z",
                "bid_amount": 450.0,
                "proposal_excerpt": "Excited to deliver this project with FastAPI",
            }
        }
        payload = service.build(
            jobs,  # type: ignore[arg-type]
            prefs,  # type: ignore[arg-type]
            limit=10,
            freelance_focus=False,
            lead_actions=lead_actions,
            applications=applications,
        )
        items = payload["items"]
        self.assertEqual(len(items), 3)
        by_id = {item["job_id"]: item for item in items}

        pitched = by_id[3]
        self.assertEqual(pitched["user_status"], "pitched")
        self.assertIsNotNone(pitched["application"])
        self.assertEqual(pitched["application"]["bid_amount"], 450.0)
        self.assertEqual(
            pitched["application"]["proposal_excerpt"],
            "Excited to deliver this project with FastAPI",
        )

        saved = by_id[2]
        self.assertEqual(saved["user_status"], "save")
        self.assertIsNone(saved["application"])

        normal = by_id[1]
        self.assertIsNone(normal["user_status"])
        self.assertIsNone(normal["application"])

        # Pitched gets the strongest action boost and should rank first.
        self.assertEqual(items[0]["job_id"], 3)


class MatchFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_feedback_high_weight_for_pitched_and_won(self) -> None:
        from unittest.mock import AsyncMock

        from backend.application.services.match_feedback import MatchFeedbackService

        session = AsyncMock()
        action_save = SimpleNamespace(status="save", job_id=1)
        job_save = SimpleNamespace(
            id=1, enrichment={"skills": ["fastapi", "docker"]}, tags=["python"]
        )

        action_pitched = SimpleNamespace(status="pitched", job_id=2)
        job_pitched = SimpleNamespace(
            id=2, enrichment={"skills": ["fastapi"]}, tags=["postgres"]
        )

        action_skip = SimpleNamespace(status="skip", job_id=3)
        job_skip = SimpleNamespace(id=3, enrichment={"skills": ["wordpress"]}, tags=[])

        mock_result = MagicMock()
        mock_result.all.return_value = [
            (action_save, job_save),
            (action_pitched, job_pitched),
            (action_skip, job_skip),
        ]
        session.execute.return_value = mock_result

        svc = MatchFeedbackService(session=session)
        weights = await svc.skill_weights("user-1", require_consent=False)
        self.assertGreater(weights.get("fastapi", 0), 0)
        self.assertLess(weights.get("wordpress", 0), 0)


if __name__ == "__main__":
    unittest.main()
