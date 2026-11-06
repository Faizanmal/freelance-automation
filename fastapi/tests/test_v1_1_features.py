from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.api.v1.jobs import get_seo_skill_directory, list_seo_directory
from app.api.v1.preferences import get_pipeline_stats
from backend.application.services.proposal_draft import ProposalDraftService


class V11BackendFeatureTests(unittest.IsolatedAsyncioTestCase):
    async def test_proposal_draft_includes_apply_email_and_subject(self) -> None:
        user = SimpleNamespace(id="u-1", email="freelancer@example.com", full_name="Alex Dev")
        prefs = SimpleNamespace(
            keywords=["python", "fastapi"],
            notes="Built high-throughput async APIs.",
            min_budget=1500,
            max_budget=4000,
        )
        job = SimpleNamespace(
            id=42,
            title="Senior FastAPI Contract Engineer",
            description="Reach out directly to founder@acmecorp.io with your portfolio.",
            url="https://news.ycombinator.com/item?id=42",
            company="Acme Corp",
            source_name="hn_hiring",
            source_id="hn-42",
            budget_min=2000.0,
            budget_max=3000.0,
            analysis_summary="Needs async Python API refactor",
            enrichment={"summary": "Async API work"},
        )

        with patch("backend.application.services.proposal_draft.any_llm_configured", return_value=False):
            result = await ProposalDraftService().draft(user=user, preferences=prefs, job=job)

        self.assertEqual(result["apply_email"], "founder@acmecorp.io")
        self.assertEqual(result["email_subject"], "Contract inquiry: Senior FastAPI Contract Engineer")
        form_fields = result["form_fields"]
        self.assertEqual(form_fields["apply_email"], "founder@acmecorp.io")
        self.assertEqual(form_fields["submit_mode"], "email_apply")

    async def test_pipeline_stats_computes_conversion_and_values(self) -> None:
        user = SimpleNamespace(id="u-pipeline")
        rows = [
            (
                SimpleNamespace(job_id=1, status="save"),
                SimpleNamespace(id=1, budget_min=1000.0, budget_max=2000.0),
            ),
            (
                SimpleNamespace(job_id=2, status="pitched"),
                SimpleNamespace(id=2, budget_min=3000.0, budget_max=3000.0),
            ),
            (
                SimpleNamespace(job_id=3, status="won"),
                SimpleNamespace(id=3, budget_min=4000.0, budget_max=6000.0),
            ),
            (
                SimpleNamespace(job_id=4, status="skip"),
                SimpleNamespace(id=4, budget_min=500.0, budget_max=500.0),
            ),
        ]
        apps = [
            SimpleNamespace(job_id=3, bid_amount=5500.0),
        ]

        actions_result = MagicMock()
        actions_result.all.return_value = rows
        apps_result = MagicMock()
        apps_result.scalars.return_value.all.return_value = apps

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[actions_result, apps_result])

        stats = await get_pipeline_stats(user=user, session=session)  # type: ignore[arg-type]

        self.assertEqual(stats["saved_count"], 1)
        self.assertEqual(stats["pitched_count"], 1)
        self.assertEqual(stats["won_count"], 1)
        self.assertEqual(stats["skipped_count"], 1)
        self.assertEqual(stats["total_engaged"], 3)
        # 2 pitched+won out of 3 engaged = 0.667
        self.assertAlmostEqual(stats["pitch_rate"], 0.667, places=3)
        # 1 won out of 2 pitched+won = 0.5
        self.assertAlmostEqual(stats["win_rate"], 0.5, places=3)
        # saved (1500) + pitched (3000) = 4500
        self.assertEqual(stats["active_pipeline_value"], 4500.0)
        # won uses bid_amount 5500.0
        self.assertEqual(stats["won_value"], 5500.0)

    async def test_seo_directory_and_skill_filtering(self) -> None:
        fake_job = SimpleNamespace(
            id=101,
            title="FastAPI + Python Backend Contractor",
            description="Contract role building Python FastAPI microservices.",
            company="Stealth AI",
            location="Remote",
            source_name="hn_hiring",
            tags=["python", "fastapi"],
            enrichment={"skills": ["python", "fastapi"]},
            budget_min=100.0,
            budget_max=140.0,
            is_expired=False,
        )
        mock_repo = MagicMock()
        mock_repo.list_recent = AsyncMock(return_value=[fake_job])
        mock_repo.to_candidate_dict = AsyncMock(
            return_value={
                "id": 101,
                "title": fake_job.title,
                "company": fake_job.company,
                "location": fake_job.location,
                "source_name": fake_job.source_name,
                "source_attribution": "Hacker News",
                "tags": fake_job.tags,
                "budget_min": 100.0,
                "budget_max": 140.0,
                "enrichment": {},
                "posted_at": "2026-11-05T10:00:00Z",
                "created_at": "2026-11-05T10:00:00Z",
                "description_excerpt": "Contract role building Python FastAPI microservices.",
            }
        )

        with patch("app.api.v1.jobs.SQLAlchemyJobRepository", return_value=mock_repo):
            index_res = await list_seo_directory(session=AsyncMock())
            self.assertEqual(index_res["total_active"], 1)
            python_cat = next(c for c in index_res["categories"] if c["slug"] == "python")
            self.assertEqual(python_cat["job_count"], 1)
            self.assertEqual(index_res["recent"][0]["company_masked"], "St••• (S*)")

            skill_res = await get_seo_skill_directory("fastapi", session=AsyncMock(), limit=10)
            self.assertEqual(skill_res["slug"], "fastapi")
            self.assertEqual(skill_res["total_matched"], 1)
            self.assertEqual(len(skill_res["items"]), 1)

            with self.assertRaises(HTTPException) as ctx:
                await get_seo_skill_directory("../invalid_slug!", session=AsyncMock(), limit=10)
            self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()

