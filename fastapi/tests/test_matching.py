import unittest
from datetime import datetime, timezone

from app.models.job import JobRecord
from app.models.preference import UserPreferences
from app.services.matching import MatchingService


def _job(**kwargs) -> JobRecord:
    defaults = {
        "id": 1,
        "source_name": "remoteok",
        "source_id": "1",
        "canonical_id": "c1",
        "title": "Senior Python FastAPI Engineer",
        "description": "Build APIs with Python and FastAPI for a funded B2B product.",
        "url": "https://example.com/1",
        "company": "Acme Labs",
        "budget_min": 4000,
        "budget_max": 7000,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "tags": ["python", "fastapi"],
    }
    defaults.update(kwargs)
    return JobRecord(**defaults)


class MatchingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MatchingService()
        self.prefs = UserPreferences(
            user_id="u1",
            keywords=["python", "fastapi"],
            exclude_keywords=[],
            sources=[],
            notification_channels=["email"],
            match_threshold=0.2,
        )

    def test_word_boundary_avoids_false_positive(self) -> None:
        job = _job(title="Angular frontend contractor", description="Ongoing React shipping work", tags=[])
        self.prefs.keywords = ["go"]
        match = self.service.score_job(job, self.prefs)
        self.assertIsNone(match)

    def test_fresh_high_budget_job_scores_well(self) -> None:
        match = self.service.score_job(_job(), self.prefs)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertGreaterEqual(match.score, 0.6)
        self.assertGreaterEqual(match.freshness_score, 0.8)
        self.assertGreaterEqual(match.client_quality_score, 0.6)

    def test_red_flags_are_detected(self) -> None:
        job = _job(description="Unpaid internship for exposure. Python FastAPI.")
        match = self.service.score_job(job, self.prefs)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertTrue(match.red_flags)


if __name__ == "__main__":
    unittest.main()
