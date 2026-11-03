import unittest
from datetime import UTC, datetime

from backend.application.services.budget_parser import (
    describe_budget,
    extract_budget,
    format_budget,
    hourly_equivalent,
    infer_period,
    normalize_period,
    passes_budget_filter,
    resolve_budget,
    stored_period,
)
from backend.application.services.duplicate_detection import JobCandidate
from backend.application.services.enrichment import EnrichmentService
from backend.application.services.matching import MatchingService
from database.models.job import JobRecord
from database.models.preference import UserPreferences


class BudgetParserUnitTests(unittest.TestCase):
    def test_extract_hourly_range(self) -> None:
        signal = extract_budget("We are looking for a Python contractor. Rate is $60-$80/hr depending on experience.")
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.minimum, 60.0)
        self.assertEqual(signal.maximum, 80.0)
        self.assertEqual(signal.period, "hourly")
        self.assertEqual(signal.currency, "USD")

    def test_extract_fixed_k_notation(self) -> None:
        signal = extract_budget("Need a landing page built. Fixed budget $3k-$5k for the project.")
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.minimum, 3000.0)
        self.assertEqual(signal.maximum, 5000.0)
        self.assertEqual(signal.period, "fixed")

    def test_extract_annual_salary(self) -> None:
        signal = extract_budget("Full-time remote role with competitive base salary: $120,000 - $140,000 / year.")
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.minimum, 120000.0)
        self.assertEqual(signal.maximum, 140000.0)
        self.assertEqual(signal.period, "annual")

    def test_infer_period_from_magnitude(self) -> None:
        self.assertEqual(infer_period(75.0), "hourly")
        self.assertEqual(infer_period(2500.0), "fixed")
        self.assertEqual(infer_period(95000.0), "annual")

    def test_normalize_period_aliases(self) -> None:
        self.assertEqual(normalize_period("hr"), "hourly")
        self.assertEqual(normalize_period("per hour"), "hourly")
        self.assertEqual(normalize_period("yearly"), "annual")
        self.assertEqual(normalize_period("project"), "fixed")

    def test_hourly_equivalent(self) -> None:
        self.assertAlmostEqual(hourly_equivalent(80.0, "hourly") or 0, 80.0)
        # $104k / 2080 hrs = $50/hr
        self.assertAlmostEqual(hourly_equivalent(104000.0, "annual") or 0, 50.0)
        self.assertIsNone(hourly_equivalent(5000.0, "fixed"))

    def test_passes_budget_filter_hourly_not_filtered_by_project_min(self) -> None:
        # Crucial bugfix: A $75/hr contract must NOT be filtered out by min_project_budget = 1500!
        passed = passes_budget_filter(
            budget_min=70.0,
            budget_max=85.0,
            period="hourly",
            min_project_budget=1500.0,
            max_project_budget=10000.0,
            min_hourly_rate=None,
        )
        self.assertTrue(passed)

    def test_passes_budget_filter_hourly_filtered_by_hourly_min(self) -> None:
        # If user explicitly sets min_hourly_rate = 50, a $40/hr job is dropped
        dropped = passes_budget_filter(
            budget_min=30.0,
            budget_max=40.0,
            period="hourly",
            min_project_budget=None,
            max_project_budget=None,
            min_hourly_rate=50.0,
        )
        self.assertFalse(dropped)

        kept = passes_budget_filter(
            budget_min=55.0,
            budget_max=75.0,
            period="hourly",
            min_project_budget=None,
            max_project_budget=None,
            min_hourly_rate=50.0,
        )
        self.assertTrue(kept)

    def test_passes_budget_filter_fixed_project(self) -> None:
        # Fixed project ($800) is filtered when min_project_budget = 1000
        dropped = passes_budget_filter(
            budget_min=500.0,
            budget_max=800.0,
            period="fixed",
            min_project_budget=1000.0,
            max_project_budget=None,
            min_hourly_rate=None,
        )
        self.assertFalse(dropped)

    def test_format_budget_labels(self) -> None:
        self.assertEqual(format_budget(60.0, 80.0, "hourly"), "$60–$80/hr")
        self.assertEqual(format_budget(5000.0, 5000.0, "fixed"), "$5,000")
        self.assertEqual(format_budget(None, 120000.0, "annual"), "up to $120,000/yr")


class EnrichmentBudgetIntegrationTests(unittest.TestCase):
    def test_heuristic_extracts_budget_from_unstructured_text(self) -> None:
        service = EnrichmentService()
        candidate = JobCandidate(
            source_name="reddit_hiring",
            source_id="r1",
            title="[Hiring] Need Python FastAPI backend developer",
            description="Looking for an experienced engineer to build microservices. Rate is $65-$85/hr. Remote.",
            url="https://reddit.com/r/forhire/1",
        )
        enrichment = service._enrich_heuristic(candidate)
        self.assertEqual(enrichment.budget_min, 65.0)
        self.assertEqual(enrichment.budget_max, 85.0)
        self.assertEqual(enrichment.budget_period, "hourly")


class MatchingBudgetIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matcher = MatchingService()
        self.prefs = UserPreferences(
            user_id="u1",
            keywords=["python", "fastapi"],
            skills=["python", "fastapi"],
            min_budget=1500.0,  # $1,500 project minimum
            min_hourly_rate=60.0,  # $60/hr rate minimum
            match_threshold=0.2,
        )

    def test_hourly_job_passes_when_above_min_hourly(self) -> None:
        hourly_job = JobRecord(
            id=101,
            source_name="serpapi_freelance",
            source_id="s101",
            canonical_id="c101",
            title="Python FastAPI Contract",
            description="FastAPI APIs development",
            url="https://example.com/101",
            budget_min=70.0,
            budget_max=90.0,
            enrichment={"skills": ["python", "fastapi"], "budget_period": "hourly"},
            tags=["python", "fastapi"],
            posted_at=datetime.now(UTC).isoformat(),
        )
        match = self.matcher.score_job(hourly_job, self.prefs)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertGreaterEqual(match.score, 0.4)

    def test_hourly_job_dropped_when_below_min_hourly(self) -> None:
        low_hourly_job = JobRecord(
            id=102,
            source_name="serpapi_freelance",
            source_id="s102",
            canonical_id="c102",
            title="Python FastAPI Junior Contract",
            description="FastAPI developer needed",
            url="https://example.com/102",
            budget_min=30.0,
            budget_max=45.0,  # below 60/hr
            enrichment={"skills": ["python", "fastapi"], "budget_period": "hourly"},
            tags=["python", "fastapi"],
            posted_at=datetime.now(UTC).isoformat(),
        )
        match = self.matcher.score_job(low_hourly_job, self.prefs)
        self.assertIsNone(match)

    def test_fixed_job_dropped_when_below_min_project_budget(self) -> None:
        low_fixed_job = JobRecord(
            id=103,
            source_name="remoteok",
            source_id="s103",
            canonical_id="c103",
            title="FastAPI Bug Fix",
            description="Quick fix",
            url="https://example.com/103",
            budget_min=300.0,
            budget_max=500.0,  # below 1500 project min
            enrichment={"skills": ["python", "fastapi"], "budget_period": "fixed"},
            tags=["python", "fastapi"],
            posted_at=datetime.now(UTC).isoformat(),
        )
        match = self.matcher.score_job(low_fixed_job, self.prefs)
        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main()

