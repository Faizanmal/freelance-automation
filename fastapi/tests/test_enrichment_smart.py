import unittest

from backend.application.services.duplicate_detection import JobCandidate
from backend.application.services.enrichment import EnrichmentService


class EnrichmentSmartTests(unittest.TestCase):
    def test_heuristic_extracts_skills_seniority_engagement(self) -> None:
        service = EnrichmentService()
        candidate = JobCandidate(
            source_name="remoteok",
            source_id="1",
            title="Senior Python FastAPI freelancer",
            description="Looking for a contractor for a FastAPI API. Remote freelance.",
            url="https://example.com/1",
            company="Acme",
        )
        enrichment = service._enrich_heuristic(candidate)
        self.assertEqual(enrichment.provider, "heuristic")
        self.assertIn("python", enrichment.skills)
        self.assertIn("fastapi", enrichment.skills)
        self.assertEqual(enrichment.seniority, "senior")
        self.assertIn(enrichment.engagement_type, {"freelance", "contract"})

    def test_short_token_go_not_matched_inside_ongoing(self) -> None:
        service = EnrichmentService()
        candidate = JobCandidate(
            source_name="remoteok",
            source_id="2",
            title="Ongoing React shipping work",
            description="Frontend contractor for an ongoing product roadmap.",
            url="https://example.com/2",
            company="Shop",
        )
        enrichment = service._enrich_heuristic(candidate)
        self.assertNotIn("go", enrichment.skills)

    def test_quality_flags_for_unpaid_course(self) -> None:
        service = EnrichmentService()
        candidate = JobCandidate(
            source_name="remoteok",
            source_id="3",
            title="Unpaid Python tutorial internship",
            description="Great course for exposure. Unpaid.",
            url="https://example.com/3",
            company="School",
        )
        enrichment = service._enrich_heuristic(candidate)
        self.assertTrue(
            {"unpaid", "course", "exposure"} & set(enrichment.quality_flags)
        )


if __name__ == "__main__":
    unittest.main()
