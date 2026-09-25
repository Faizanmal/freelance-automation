import unittest
from datetime import datetime, timezone

from app.models.job import JobRecord
from app.models.preference import UserPreferences
from backend.application.services.lead_findings import LeadFindingsService


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


class LeadFindingsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = LeadFindingsService()
        self.prefs = UserPreferences(
            user_id="u1",
            keywords=["python", "fastapi"],
            exclude_keywords=[],
            sources=[],
            notification_channels=["email"],
            match_threshold=0.2,
        )

    def test_strong_lead_suggests_draft_bid(self) -> None:
        payload = self.service.build([_job()], self.prefs, limit=5, freelance_focus=False)
        self.assertEqual(payload["total_findings"], 1)
        item = payload["items"][0]
        self.assertEqual(item["action"], "draft_bid")
        self.assertTrue(item["why"])
        self.assertTrue(item["signals"])
        self.assertIn(item["action"], payload["action_counts"])

    def test_risky_lead_suggests_skip(self) -> None:
        job = _job(
            description="Unpaid internship for exposure. Guaranteed income. Python FastAPI.",
            budget_min=None,
            budget_max=None,
        )
        payload = self.service.build([job], self.prefs, limit=5, freelance_focus=False)
        self.assertEqual(payload["items"][0]["action"], "skip")
        self.assertTrue(payload["items"][0]["risks"])

    def test_freelance_focus_boosts_marketplace(self) -> None:
        marketplace = _job(
            id=2,
            source_name="freelancer",
            source_id="99",
            canonical_id="c99",
            title="Python FastAPI microservice",
            description="Need a freelancer for a short-term FastAPI contract. Fixed-price.",
            budget_min=500,
            budget_max=1500,
        )
        full_time = _job(
            id=3,
            source_name="himalayas",
            source_id="88",
            canonical_id="c88",
            title="Python FastAPI Engineer",
            description="Full-time salary role with benefits package and 401k. Python FastAPI.",
            budget_min=None,
            budget_max=None,
            location="United States",
        )
        payload = self.service.build(
            [full_time, marketplace],
            self.prefs,
            limit=5,
            freelance_focus=True,
        )
        self.assertTrue(payload["freelance_focus"])
        self.assertGreaterEqual(payload["total_findings"], 1)
        top = payload["items"][0]
        self.assertEqual(top["source_name"], "freelancer")
        self.assertGreaterEqual(top["freelance_fit"], 0.55)
        self.assertTrue(top["freelance_benefits"])
        self.assertTrue(top["freelance_benefits_line"])

    def test_freelance_focus_downranks_employee_posting(self) -> None:
        full_time = _job(
            description="Full-time permanent salary role with benefits package. Python FastAPI.",
            budget_min=None,
            budget_max=None,
        )
        payload = self.service.build([full_time], self.prefs, limit=5, freelance_focus=True)
        if payload["items"]:
            item = payload["items"][0]
            self.assertTrue(item["employment_risks"])
            self.assertIn(item["action"], {"watch", "skip"})


if __name__ == "__main__":
    unittest.main()
