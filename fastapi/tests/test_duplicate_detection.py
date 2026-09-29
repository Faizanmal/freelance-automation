import unittest

from backend.application.services.duplicate_detection import (
    DuplicateDetectionService,
    JobCandidate,
)


class DuplicateDetectionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DuplicateDetectionService()

    def test_exact_url_duplicate_is_detected(self) -> None:
        canonical = JobCandidate(
            source_name="upwork",
            source_id="upwork-1",
            title="Senior Python Developer",
            description="Build APIs for a B2B analytics platform.",
            url="https://example.com/jobs/1",
            company="Acme Labs",
            budget_min=5000,
            budget_max=7000,
            posted_at="2026-06-20T10:00:00Z",
        )
        incoming = JobCandidate(
            source_name="freelancer",
            source_id="freelancer-99",
            title="Senior Python Engineer",
            description="Need help building APIs for a B2B analytics platform.",
            url="https://example.com/jobs/1",
            company="Acme Labs",
            budget_min=5500,
            budget_max=7200,
            posted_at="2026-06-21T09:00:00Z",
        )

        decision = self.service.detect_duplicate(canonical, incoming)

        self.assertTrue(decision.is_duplicate)
        self.assertGreaterEqual(decision.confidence, 0.95)

    def test_similar_jobs_merge_with_source_history(self) -> None:
        canonical = JobCandidate(
            source_name="upwork",
            source_id="upwork-2",
            title="Full Stack Developer",
            description="Build an internal dashboard using React and Django.",
            url="https://example.com/jobs/2",
            company="Northwind",
            budget_min=4000,
            budget_max=6000,
            posted_at="2026-06-20T10:00:00Z",
        )
        incoming = JobCandidate(
            source_name="indeed",
            source_id="indeed-2",
            title="Full Stack Engineer",
            description="Develop an internal dashboard with React and Django for analytics.",
            url="https://example.com/jobs/2-copy",
            company="Northwind Analytics",
            budget_min=4200,
            budget_max=6200,
            posted_at="2026-06-22T10:00:00Z",
        )

        decision = self.service.detect_duplicate(canonical, incoming)
        merged = self.service.merge_duplicate(canonical, incoming, decision)

        self.assertGreaterEqual(decision.confidence, 0.78)
        self.assertEqual(merged.source_history[0].source_name, "upwork")
        self.assertEqual(merged.source_history[1].source_name, "indeed")
