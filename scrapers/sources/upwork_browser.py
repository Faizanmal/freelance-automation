from __future__ import annotations

import logging
from typing import Any

from backend.domain.models import JobOpportunity, SourceHealthStatus
from scrapers.core.base_scraper import BaseScraper
from scrapers.core.navigation import wait_for_element

logger = logging.getLogger(__name__)


class UpworkBrowserScraper(BaseScraper):
    """Playwright-powered browser scraper for Upwork to bypass strict API rate limits."""

    name = "upwork_browser"

    async def login(self) -> None:
        if not self.page:
            raise RuntimeError("Page is not available")

        logger.info("Attempting login to Upwork (relying heavily on cookies)")
        await self.page.goto("https://www.upwork.com/ab/account-security/login")

        try:
            await wait_for_element(self.page, ".nav-item-user", timeout=5)
            logger.info("Successfully identified logged-in state via cookies.")
        except TimeoutError:
            logger.warning(
                "Could not find user avatar, login might be required manually."
            )

    async def search(self, query: str, **kwargs: Any) -> None:
        if not self.page:
            raise RuntimeError("Page is not available")

        url = f"https://www.upwork.com/nx/search/jobs/?q={query}"
        logger.info("Navigating to Upwork search: %s", url)
        await self.page.goto(url)
        try:
            await wait_for_element(
                self.page, "section[data-test='job-tile-list']", timeout=15
            )
        except TimeoutError:
            logger.warning(
                "Job list not found, might have hit captcha or anti-bot mechanism."
            )
            if hasattr(self, "capture_screenshot"):
                await self.capture_screenshot("upwork_search_failure")

    async def extract_jobs(self) -> list[dict[str, Any]]:
        if not self.page:
            return []

        tiles = await self.page.locator("section.up-card-section").all()
        raw_jobs = []
        limit = getattr(self, "limit", 20)

        for tile in tiles:
            try:
                title_el = tile.locator("h2.job-tile-title a")
                title = await title_el.inner_text()
                url = await title_el.get_attribute("href")
                desc = await tile.locator(
                    "div[data-test='job-description-text']"
                ).inner_text()

                raw_jobs.append(
                    {
                        "title": title.strip(),
                        "url": f"https://www.upwork.com{url}" if url else "",
                        "description": desc.strip(),
                    }
                )
            except (AttributeError, TypeError, ValueError) as e:
                logger.debug("Failed to parse a job tile: %s", e)

            if len(raw_jobs) >= limit:
                break

        return raw_jobs

    async def fetch_jobs(self, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        """Implementation for IJobSourceAdapter"""
        self.limit = limit
        query = kwargs.get("query", "python developer")
        await self.login()
        await self.search(query)
        return await self.extract_jobs()

    async def normalize(self, raw_job: dict[str, Any]) -> JobOpportunity:
        """Implementation for IJobSourceAdapter"""
        return JobOpportunity(
            source=self.name,
            external_id=raw_job["url"],
            title=raw_job["title"],
            company="Upwork client",
            location="Remote",
            description=raw_job["description"],
            url=raw_job["url"],
        )

    async def health_check(self) -> SourceHealthStatus:
        """Implementation for IJobSourceAdapter"""
        try:
            await self.login()
            is_healthy = True
            msg = None
        except (RuntimeError, TimeoutError, OSError) as e:
            is_healthy = False
            msg = str(e)

        return SourceHealthStatus(
            source=self.name, is_healthy=is_healthy, error_message=msg
        )

    async def save(self, job: dict[str, Any]) -> None:
        logger.info("UpworkBrowserScraper discovered job: %s", job["title"])
