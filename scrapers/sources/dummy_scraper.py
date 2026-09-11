from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from scrapers.core.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class DummyScraper(BaseScraper):
    async def login(self) -> None:
        logger.info("Dummy login: no action taken")

    async def search(self, query: str, **kwargs: Any) -> None:
        logger.info("Dummy search for query=%s", query)

    async def extract_jobs(self) -> list[dict[str, Any]]:
        logger.info("Dummy extract_jobs called")
        return [
            {
                "title": "Sample Freelance Job",
                "company": "Example Co",
                "location": "Remote",
                "description": "This is a mock job listing for the generic scraper framework.",
                "url": "https://example.com/jobs/1",
                "posted_at": "2026-06-30T00:00:00Z",
            }
        ]

    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        logger.info("Normalizing job %s", raw_job["title"])
        return {
            "source": "dummy",
            "external_id": raw_job["url"],
            "title": raw_job["title"],
            "company": raw_job["company"],
            "location": raw_job["location"],
            "description": raw_job["description"],
            "url": raw_job["url"],
            "posted_at": raw_job["posted_at"],
        }

    async def save(self, job: dict[str, Any]) -> None:
        path = Path(self.storage_dir) / "dummy_job.json"
        path.write_text(str(job), encoding="utf-8")
        logger.info("Saved normalized job to %s", path)
