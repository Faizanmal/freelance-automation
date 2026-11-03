"""Save/Skip lead actions filter findings and persist per user."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.application.services.lead_findings import LeadFindingsService


def _job(job_id: int, title: str = "Role") -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        title=title,
        company="Acme",
        source_name="serpapi_freelance",
        url=f"https://example.com/{job_id}",
        description="Looking for a freelance python contractor for a short project",
        location="Remote",
        tags=["python", "freelance"],
        enrichment={},
        seniority=None,
        posted_at=None,
        budget_min=None,
        budget_max=None,
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
        )
        matcher = MagicMock()
        match_keep = MagicMock(
            job=jobs[0],
            score=0.9,
            matched_keywords=["python"],
            reasons=["kw"],
            freshness_score=0.8,
            client_quality_score=0.7,
            red_flags=[],
        )
        match_skip = MagicMock(
            job=jobs[1],
            score=0.85,
            matched_keywords=["python"],
            reasons=["kw"],
            freshness_score=0.7,
            client_quality_score=0.6,
            red_flags=[],
        )
        matcher.rank_jobs.return_value = [match_keep, match_skip]
        service = LeadFindingsService(matcher=matcher)
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
        )
        matcher = MagicMock()
        matcher.rank_jobs.return_value = [
            MagicMock(job=jobs[0], score=0.9, matched_keywords=["python"], reasons=["kw"], freshness_score=0.8, client_quality_score=0.7, red_flags=[]),
            MagicMock(job=jobs[1], score=0.9, matched_keywords=["python"], reasons=["kw"], freshness_score=0.8, client_quality_score=0.7, red_flags=[]),
            MagicMock(job=jobs[2], score=0.8, matched_keywords=["python"], reasons=["kw"], freshness_score=0.8, client_quality_score=0.7, red_flags=[]),
        ]
        service = LeadFindingsService(matcher=matcher)
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
        # Pitched lead (job 3) has highest boost (1.2) so it ranks first despite base score 0.8
        self.assertEqual(items[0]["job_id"], 3)
        self.assertEqual(items[0]["user_status"], "pitched")
        self.assertIsNotNone(items[0]["application"])
        self.assertEqual(items[0]["application"]["bid_amount"], 450.0)
        self.assertEqual(items[0]["application"]["proposal_excerpt"], "Excited to deliver this project with FastAPI")

        # Saved lead (job 2) ranks second (boost 1.0)
        self.assertEqual(items[1]["job_id"], 2)
        self.assertEqual(items[1]["user_status"], "save")
        self.assertIsNone(items[1]["application"])

        # Unactioned lead (job 1) ranks last (boost 0.0)
        self.assertEqual(items[2]["job_id"], 1)
        self.assertIsNone(items[2]["user_status"])
        self.assertIsNone(items[2]["application"])


class MatchFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_feedback_high_weight_for_pitched_and_won(self) -> None:
        from unittest.mock import AsyncMock
        from backend.application.services.match_feedback import MatchFeedbackService

        session = AsyncMock()
        action_save = SimpleNamespace(status="save", job_id=1)
        job_save = SimpleNamespace(id=1, enrichment={"skills": ["fastapi", "docker"]}, tags=["python"])

        action_pitched = SimpleNamespace(status="pitched", job_id=2)
        job_pitched = SimpleNamespace(id=2, enrichment={"skills": ["fastapi"]}, tags=["postgres"])

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
        weights = await svc.skill_weights("user-1")

        # fastapi was saved once (+0.04) and pitched once (+0.06) -> +0.10
        self.assertAlmostEqual(weights["fastapi"], 0.10)
        # postgres was pitched once -> +0.06
        self.assertAlmostEqual(weights["postgres"], 0.06)
        # wordpress was skipped once -> -0.04
        self.assertAlmostEqual(weights["wordpress"], -0.04)


if __name__ == "__main__":
    unittest.main()
