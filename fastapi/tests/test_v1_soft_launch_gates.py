"""W4 soft-launch gates G1–G6 / G8 as code-level checks (no live host required)."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.ingestion.sources import MARKETPLACE_SOURCES, V1_DEFAULT_HUNTERS

from backend.application.services.digest_service import is_digest_due
from backend.application.services.listing_presentation import public_job_payload
from backend.application.services.scrape_service import ScrapeService
from config.settings import Settings


class SoftLaunchGateTests(unittest.IsolatedAsyncioTestCase):
    def test_g3_default_hunters_exclude_marketplaces(self) -> None:
        self.assertEqual(
            V1_DEFAULT_HUNTERS,
            ("serpapi_freelance", "serpapi_jobs", "serpapi_companies"),
        )
        field = Settings.model_fields["scrape_sources"]
        default = field.default
        self.assertEqual(
            default,
            "serpapi_freelance,serpapi_jobs,serpapi_companies",
        )
        for source in MARKETPLACE_SOURCES:
            self.assertNotIn(source, V1_DEFAULT_HUNTERS)
            self.assertNotIn(source, default.split(","))

    def test_g4_listings_keep_excerpt_attribution_and_original_url(self) -> None:
        long_desc = "A" * 500 + " freelance contractor needed for API work."
        payload = public_job_payload(
            {
                "title": "API contractor",
                "description": long_desc,
                "url": "https://boards.greenhouse.io/acme/jobs/1",
                "source_name": "serpapi_companies",
            }
        )
        self.assertEqual(
            payload["apply_url"], "https://boards.greenhouse.io/acme/jobs/1"
        )
        self.assertIn("source_attribution", payload)
        self.assertLess(len(payload["description_excerpt"]), len(long_desc))
        self.assertNotEqual(payload["description_excerpt"], long_desc)

    def test_g2_digest_show_clock_due_check(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        local = datetime(2026, 10, 14, 9, 2, tzinfo=ZoneInfo("UTC"))
        prefs = SimpleNamespace(
            digest_mode=True,
            timezone="UTC",
            digest_days=["wed"],
            digest_time_local="09:00",
            last_digest_at=None,
        )
        self.assertTrue(is_digest_due(prefs, now_utc=local))

        prefs_off = SimpleNamespace(
            digest_mode=False,
            timezone="UTC",
            digest_days=["wed"],
            digest_time_local="09:00",
            last_digest_at=None,
        )
        self.assertFalse(is_digest_due(prefs_off, now_utc=local))

    def test_g5_commercial_free_limits(self) -> None:
        from backend.application.services.billing import PLANS

        free = PLANS["free"]
        pro = PLANS["pro"]
        self.assertFalse(free.marketplace)
        self.assertEqual(free.daily_scrape_runs, 3)
        self.assertEqual(free.max_digest, 5)
        self.assertEqual(free.scrape_limit, 15)
        self.assertEqual(free.allowed_channels, frozenset({"email"}))

        self.assertTrue(pro.marketplace)
        self.assertEqual(pro.daily_scrape_runs, 50)
        self.assertEqual(pro.max_digest, 25)
        self.assertEqual(pro.scrape_limit, 100)

    async def test_g6_hunter_failure_does_not_abort_wave(self) -> None:
        session = AsyncMock()
        service = ScrapeService(session)

        good = MagicMock()
        good.fetch = AsyncMock(
            return_value=[
                SimpleNamespace(
                    source_name="serpapi_freelance",
                    source_id="1",
                    title="Ok",
                    url="https://example.com/1",
                    description="freelance",
                    company="A",
                    metadata={},
                )
            ]
        )
        bad = MagicMock()
        bad.fetch = AsyncMock(side_effect=RuntimeError("hunter down"))

        class GoodSource:
            def __init__(self) -> None:
                self.fetch = good.fetch

        class BadSource:
            def __init__(self) -> None:
                self.fetch = bad.fetch

        with (
            patch(
                "backend.application.services.scrape_service.SOURCE_REGISTRY",
                {
                    "serpapi_freelance": GoodSource,
                    "serpapi_jobs": BadSource,
                },
            ),
            patch.object(
                service.ingestion,
                "ingest",
                new=AsyncMock(return_value={"action": "ingested", "job_id": 1}),
            ),
        ):
            summary = await service.run(
                ["serpapi_freelance", "serpapi_jobs"],
                limit=5,
                notify_matches=False,
            )

        self.assertIn("error", summary["sources"]["serpapi_jobs"])
        self.assertEqual(
            summary["sources"]["serpapi_freelance"]["ingested"], 1
        )
        self.assertEqual(summary["total_ingested"], 1)

    def test_g1_auth_nav_and_leads_primary_cta_in_frontend(self) -> None:
        root = Path(__file__).resolve().parents[2]
        nav_file = root / "frontend" / "src" / "components" / "nav-config.ts"
        nav_content = (
            nav_file.read_text(encoding="utf-8")
            if nav_file.exists()
            else (root / "frontend" / "src" / "components" / "site-header.tsx").read_text(
                encoding="utf-8"
            )
        )
        leads = (root / "frontend" / "src" / "app" / "leads" / "page.tsx").read_text(
            encoding="utf-8"
        )
        self.assertIn('label: "Hunt Rules"', nav_content)
        self.assertNotIn('label: "Sources"', nav_content)
        self.assertIn("Open original", leads)
        open_idx = leads.index("Open original")
        draft_idx = leads.index("Draft bid")
        self.assertLess(open_idx, draft_idx)


if __name__ == "__main__":
    unittest.main()
