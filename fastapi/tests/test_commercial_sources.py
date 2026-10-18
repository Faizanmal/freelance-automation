"""Remaining: commercial allowlists exclude restricted + experimental browsers."""

from __future__ import annotations

import unittest

from app.ingestion.sources import (
    COMMERCIAL_FREE_SOURCES,
    COMMERCIAL_PRO_SOURCES,
    EXPERIMENTAL_BROWSER_SOURCES,
    MARKETPLACE_SOURCES,
    POST_V1_HUNTERS,
    RESTRICTED_SOURCES,
    V1_DEFAULT_HUNTERS,
)


class CommercialSourceAllowlistTests(unittest.TestCase):
    def test_v1_default_hunters_are_serpapi_spine(self) -> None:
        self.assertEqual(
            V1_DEFAULT_HUNTERS,
            ("serpapi_freelance", "serpapi_jobs", "serpapi_companies"),
        )
        for source in MARKETPLACE_SOURCES:
            self.assertNotIn(source, V1_DEFAULT_HUNTERS)
        for source in POST_V1_HUNTERS:
            self.assertNotIn(source, V1_DEFAULT_HUNTERS)

    def test_post_v1_includes_reddit_hiring(self) -> None:
        self.assertIn("reddit_hiring", POST_V1_HUNTERS)
        self.assertIn("reddit_hiring", COMMERCIAL_FREE_SOURCES)

    def test_free_sources_include_v1_spine(self) -> None:
        for source in V1_DEFAULT_HUNTERS:
            self.assertIn(source, COMMERCIAL_FREE_SOURCES)
        for source in ("remoteok", "arbeitnow", "himalayas", "jobicy"):
            self.assertIn(source, COMMERCIAL_FREE_SOURCES)

    def test_pro_includes_marketplaces_and_maps(self) -> None:
        for source in ("upwork", "freelancer", "serpapi_maps"):
            self.assertIn(source, COMMERCIAL_PRO_SOURCES)
        for source in V1_DEFAULT_HUNTERS:
            self.assertIn(source, COMMERCIAL_PRO_SOURCES)

    def test_browser_sources_are_experimental_not_pro(self) -> None:
        for source in EXPERIMENTAL_BROWSER_SOURCES:
            self.assertNotIn(source, COMMERCIAL_PRO_SOURCES)
            self.assertNotIn(source, COMMERCIAL_FREE_SOURCES)

    def test_restricted_sources_excluded_from_commercial(self) -> None:
        for source in RESTRICTED_SOURCES:
            self.assertNotIn(source, COMMERCIAL_FREE_SOURCES)
            self.assertNotIn(source, COMMERCIAL_PRO_SOURCES)


if __name__ == "__main__":
    unittest.main()
