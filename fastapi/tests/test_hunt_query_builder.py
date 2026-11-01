import unittest
from unittest.mock import MagicMock

from backend.application.services.hunt_query_builder import (
    compose_freelance_query,
    compose_jobs_query,
    skills_from_preferences,
)


class HuntQueryBuilderTests(unittest.TestCase):
    def test_skills_prefer_skills_field(self) -> None:
        prefs = MagicMock()
        prefs.skills = ["React", "TypeScript"]
        prefs.keywords = ["graphql"]
        self.assertEqual(
            skills_from_preferences(prefs),
            ["react", "typescript", "graphql"],
        )

    def test_legacy_keywords_used_when_skills_empty(self) -> None:
        prefs = MagicMock()
        prefs.skills = []
        prefs.keywords = ["Python", "FastAPI"]
        self.assertEqual(skills_from_preferences(prefs), ["python", "fastapi"])

    def test_compose_queries_include_skills(self) -> None:
        freelance = compose_freelance_query(["python", "fastapi"], base="fallback")
        jobs = compose_jobs_query(["python", "fastapi"], base="fallback")
        self.assertIn("python", freelance)
        self.assertIn("fastapi", freelance)
        self.assertIn("freelancer", freelance)
        self.assertIn("python", jobs)
        self.assertIn("remote", jobs)

    def test_compose_falls_back_without_skills(self) -> None:
        self.assertEqual(
            compose_freelance_query([], base="DEFAULT FREELANCE"),
            "DEFAULT FREELANCE",
        )


if __name__ == "__main__":
    unittest.main()
