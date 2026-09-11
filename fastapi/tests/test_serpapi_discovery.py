import unittest
from unittest.mock import AsyncMock, patch

from app.integrations import serpapi_discovery


class SerpApiDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_not_configured_raises(self) -> None:
        with patch("app.integrations.serpapi_discovery.get_settings") as settings:
            settings.return_value.serpapi_api_key = None
            with self.assertRaises(serpapi_discovery.SourceNotConfiguredError):
                await serpapi_discovery.search_discovery(mode="freelance", limit=5)

    async def test_freelance_filters_noise_and_maps_rows(self) -> None:
        payload = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Looking for Python freelancer for FastAPI project",
                    "link": "https://example.com/hire-python",
                    "snippet": "Need a contractor to build APIs this month.",
                    "displayed_link": "example.com",
                },
                {
                    "position": 2,
                    "title": "How to become a freelancer course",
                    "link": "https://example.com/course",
                    "snippet": "Tutorial for beginners",
                },
            ]
        }
        with (
            patch("app.integrations.serpapi_discovery.get_settings") as settings,
            patch(
                "app.integrations.serpapi_discovery._get_json",
                new=AsyncMock(return_value=payload),
            ),
        ):
            settings.return_value.serpapi_api_key = "test-key"
            settings.return_value.serpapi_freelance_query = "python freelancer"
            settings.return_value.serpapi_gl = "us"
            settings.return_value.serpapi_hl = "en"
            rows = await serpapi_discovery.search_discovery(mode="freelance", limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Looking for Python freelancer for FastAPI project")
        self.assertEqual(rows[0]["company"], "example.com")
        self.assertIn("freelance", rows[0]["tags"])

    async def test_jobs_engine_maps_apply_link(self) -> None:
        payload = {
            "jobs_results": [
                {
                    "title": "Remote React Developer",
                    "company_name": "Acme",
                    "description": "Build UI",
                    "job_id": "abc123",
                    "location": "Anywhere",
                    "apply_options": [{"link": "https://boards.example.com/jobs/1"}],
                    "detected_extensions": {"schedule_type": "Full-time", "posted_at": "2 days ago"},
                    "extensions": ["Remote"],
                }
            ]
        }
        with (
            patch("app.integrations.serpapi_discovery.get_settings") as settings,
            patch(
                "app.integrations.serpapi_discovery._get_json",
                new=AsyncMock(return_value=payload),
            ),
        ):
            settings.return_value.serpapi_api_key = "test-key"
            settings.return_value.serpapi_jobs_query = "react remote"
            settings.return_value.serpapi_location = ""
            settings.return_value.serpapi_gl = "us"
            settings.return_value.serpapi_hl = "en"
            rows = await serpapi_discovery.search_discovery(mode="jobs", limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://boards.example.com/jobs/1")
        self.assertEqual(rows[0]["company"], "Acme")
        self.assertEqual(rows[0]["source_id"], "abc123")

    async def test_companies_accepts_allowlisted_tenants_rejects_high_traffic(self) -> None:
        payload = {
            "organic_results": [
                {
                    "title": "Careers at Apex Systems",
                    "link": "https://www.apexsystems.com/careers",
                    "snippet": "Join our team",
                },
                {
                    "title": "Spark Brighter roles",
                    "link": "https://sparkbrighter-04a99f.careers.hibob.com/",
                    "snippet": "Open positions",
                },
                {
                    "title": "Python jobs on LinkedIn",
                    "link": "https://www.linkedin.com/jobs/view/123",
                    "snippet": "Browse openings",
                },
                {
                    "title": "Greenhouse board",
                    "link": "https://boards.greenhouse.io/acme",
                    "snippet": "We're hiring",
                },
                {
                    "title": "SmartRecruiters",
                    "link": "https://jobs.smartrecruiters.com/Acme/123",
                    "snippet": "Open roles",
                },
            ]
        }
        with (
            patch("app.integrations.serpapi_discovery.get_settings") as settings,
            patch(
                "app.integrations.serpapi_discovery._get_json",
                new=AsyncMock(return_value=payload),
            ),
        ):
            settings.return_value.serpapi_api_key = "test-key"
            settings.return_value.serpapi_companies_query = "python careers"
            settings.return_value.serpapi_company_sites = ""
            settings.return_value.serpapi_gl = "us"
            settings.return_value.serpapi_hl = "en"
            rows = await serpapi_discovery.search_discovery(
                mode="companies",
                query="python careers site:apexsystems.com",
                limit=10,
            )

        urls = [row["url"] for row in rows]
        self.assertIn("https://www.apexsystems.com/careers", urls)
        self.assertIn("https://sparkbrighter-04a99f.careers.hibob.com/", urls)
        self.assertTrue(all("linkedin.com" not in url for url in urls))
        self.assertTrue(all("greenhouse.io" not in url for url in urls))
        self.assertTrue(all("smartrecruiters.com" not in url for url in urls))

    async def test_companies_batches_site_queries(self) -> None:
        sites = [f"company{i}.example" for i in range(10)]
        keyword = '(careers OR jobs) python'
        get_json = AsyncMock(
            side_effect=[
                {
                    "organic_results": [
                        {
                            "title": "Careers A",
                            "link": "https://company0.example/careers",
                            "snippet": "Open roles",
                        }
                    ]
                },
                {
                    "organic_results": [
                        {
                            "title": "Careers B",
                            "link": "https://company8.example/jobs",
                            "snippet": "We're hiring",
                        }
                    ]
                },
            ]
        )
        with (
            patch("app.integrations.serpapi_discovery.get_settings") as settings,
            patch("app.integrations.serpapi_discovery._get_json", new=get_json),
            patch(
                "app.integrations.serpapi_discovery.resolve_company_career_sites",
                return_value=sites,
            ),
        ):
            settings.return_value.serpapi_api_key = "test-key"
            settings.return_value.serpapi_companies_query = keyword
            settings.return_value.serpapi_gl = "us"
            settings.return_value.serpapi_hl = "en"
            rows = await serpapi_discovery.search_discovery(mode="companies", limit=5)

        self.assertEqual(get_json.await_count, 2)
        first_q = get_json.await_args_list[0].args[0]["q"]
        second_q = get_json.await_args_list[1].args[0]["q"]
        self.assertIn("site:company0.example", first_q)
        self.assertIn("site:company7.example", first_q)
        self.assertNotIn("site:company8.example", first_q)
        self.assertIn("site:company8.example", second_q)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["company"], "company0.example")
        self.assertEqual(rows[1]["company"], "company8.example")

    def test_build_companies_site_queries_batches(self) -> None:
        queries = serpapi_discovery.build_companies_site_queries(
            keyword_query="careers python",
            sites=["a.com", "b.com", "c.com"],
            batch_size=2,
        )
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0], "careers python (site:a.com OR site:b.com)")
        self.assertEqual(queries[1], "careers python (site:c.com)")

    def test_resolve_company_sites_env_override(self) -> None:
        sites = serpapi_discovery.resolve_company_career_sites("ApexSystems.com, https://ZeekTek.com/careers")
        self.assertEqual(sites, ["apexsystems.com", "zeektek.com"])

    async def test_maps_maps_local_results(self) -> None:
        payload = {
            "local_results": [
                {
                    "title": "Northwind Software",
                    "place_id": "ChIJtest123",
                    "address": "1 Market St, SF",
                    "phone": "+1 555-0100",
                    "website": "https://northwind.example",
                    "type": "Software company",
                    "rating": 4.8,
                    "reviews": 42,
                },
                {
                    "title": "No Contact Cafe",
                    "place_id": "ChIJnone",
                    "address": "2 Side St",
                },
            ]
        }
        with (
            patch("app.integrations.serpapi_discovery.get_settings") as settings,
            patch(
                "app.integrations.serpapi_discovery._get_json",
                new=AsyncMock(return_value=payload),
            ),
        ):
            settings.return_value.serpapi_api_key = "test-key"
            settings.return_value.serpapi_maps_query = "software agencies"
            settings.return_value.serpapi_maps_ll = "@37.77,-122.42,14z"
            settings.return_value.serpapi_hl = "en"
            rows = await serpapi_discovery.search_discovery(mode="maps", limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company"], "Northwind Software")
        self.assertEqual(rows[0]["url"], "https://northwind.example")
        self.assertIn("outreach", rows[0]["tags"])


if __name__ == "__main__":
    unittest.main()
