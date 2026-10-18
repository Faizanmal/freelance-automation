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


if __name__ == "__main__":
    unittest.main()
