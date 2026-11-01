import unittest
from datetime import UTC, datetime

from backend.application.services.matching import MatchingService
from database.models.job import JobRecord
from database.models.preference import UserPreferences


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
        "posted_at": datetime.now(UTC).isoformat(),
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
        job = _job(
            title="Angular frontend contractor",
            description="Ongoing React shipping work",
            tags=[],
        )
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

    def test_skills_field_matches_without_keywords(self) -> None:
        self.prefs.keywords = []
        self.prefs.skills = ["python", "fastapi"]
        match = self.service.score_job(_job(), self.prefs)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("python", match.matched_keywords)

    def test_experience_level_boosts_senior_fit(self) -> None:
        self.prefs.skills = ["python"]
        self.prefs.keywords = []
        self.prefs.experience_level = "senior"
        senior = self.service.score_job(
            _job(title="Senior Python Engineer", seniority="senior"), self.prefs
        )
        junior = self.service.score_job(
            _job(
                id=2,
                source_id="2",
                canonical_id="c2",
                title="Junior Python intern",
                seniority="junior",
                description="Entry-level Python internship for graduates.",
            ),
            self.prefs,
        )
        self.assertIsNotNone(senior)
        self.assertIsNotNone(junior)
        assert senior is not None and junior is not None
        self.assertGreater(senior.score, junior.score)

    def test_feedback_weights_boost_saved_skills(self) -> None:
        self.prefs.skills = ["python"]
        self.prefs.keywords = []
        self.prefs.match_threshold = 0.1
        base = self.service.score_job(_job(tags=["python"]), self.prefs)
        boosted = self.service.score_job(
            _job(tags=["python"], enrichment={"skills": ["python"]}),
            self.prefs,
            skill_weights={"python": 0.12},
        )
        self.assertIsNotNone(base)
        self.assertIsNotNone(boosted)
        assert base is not None and boosted is not None
        self.assertGreater(boosted.score, base.score)

    def test_quality_flags_reduce_score(self) -> None:
        self.prefs.skills = ["python"]
        self.prefs.keywords = []
        self.prefs.match_threshold = 0.05
        clean = self.service.score_job(_job(), self.prefs)
        flagged = self.service.score_job(
            _job(
                id=9,
                source_id="9",
                canonical_id="c9",
                enrichment={"skills": ["python"], "quality_flags": ["unpaid", "course"]},
            ),
            self.prefs,
        )
        self.assertIsNotNone(clean)
        self.assertIsNotNone(flagged)
        assert clean is not None and flagged is not None
        self.assertGreater(clean.score, flagged.score)


if __name__ == "__main__":
    unittest.main()

