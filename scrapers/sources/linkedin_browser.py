from __future__ import annotations

import logging
from typing import Any

from backend.domain.models import JobOpportunity, SourceHealthStatus
from scrapers.core.base_scraper import BaseScraper
from scrapers.core.navigation import wait_for_element

logger = logging.getLogger(__name__)

class LinkedInBrowserScraper(BaseScraper):
    """Playwright-powered browser scraper for LinkedIn Jobs."""
    
    name = "linkedin_browser"
    
    async def login(self) -> None:
        if not self.page:
            raise RuntimeError("Page is not available")
            
        logger.info("Navigating to LinkedIn login")
        await self.page.goto("https://www.linkedin.com/login")
        
        try:
            await wait_for_element(self.page, "#global-nav-typeahead", timeout=5)
            logger.info("Already logged in via cookies.")
        except Exception:  # noqa: BLE001
            logger.warning("Not logged in. A manual login with headless=False is likely required.")
            
    async def search(self, query: str, **kwargs: Any) -> None:
        if not self.page:
            raise RuntimeError("Page is not available")
            
        url = f"https://www.linkedin.com/jobs/search/?keywords={query}&f_WT=2"
        logger.info("Navigating to LinkedIn jobs: %s", url)
        await self.page.goto(url)
        
        try:
            await wait_for_element(self.page, ".scaffold-layout__list", timeout=15)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load job list. Captcha or auth failure.")
            if hasattr(self, "capture_screenshot"):
                await self.capture_screenshot("linkedin_search_failure")

    async def extract_jobs(self) -> list[dict[str, Any]]:
        if not self.page:
            return []
            
        cards = await self.page.locator(".job-card-container").all()
        raw_jobs = []
        limit = getattr(self, "limit", 20)
        
        for card in cards:
            try:
                title_el = card.locator(".job-card-list__title")
                title = await title_el.inner_text()
                url = await title_el.get_attribute("href")
                company = await card.locator(".job-card-container__primary-description").inner_text()
                
                raw_jobs.append({
                    "title": title.strip(),
                    "company": company.strip(),
                    "url": f"https://www.linkedin.com{url.split('?')[0]}" if url else "",
                    "description": ""  # LinkedIn list view doesn't have full desc without clicking
                })
            except Exception as e:  # noqa: BLE001
                logger.debug("Failed to parse LinkedIn job card: %s", e)
                
            if len(raw_jobs) >= limit:
                break
                
        return raw_jobs

    async def fetch_jobs(self, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        """Implementation for IJobSourceAdapter"""
        self.limit = limit
        query = kwargs.get("query", "software engineer")
        await self.login()
        await self.search(query)
        return await self.extract_jobs()

    async def normalize(self, raw_job: dict[str, Any]) -> JobOpportunity:
        """Implementation for IJobSourceAdapter"""
        return JobOpportunity(
            source=self.name,
            external_id=raw_job["url"],
            title=raw_job["title"],
            company=raw_job.get("company", "Unknown"),
            location="Remote",
            description=raw_job.get("description", ""),
            url=raw_job["url"],
        )

    async def health_check(self) -> SourceHealthStatus:
        """Implementation for IJobSourceAdapter"""
        try:
            await self.login()
            is_healthy = True
            msg = None
        except Exception as e:  # noqa: BLE001
            is_healthy = False
            msg = str(e)
            
        return SourceHealthStatus(
            source=self.name,
            is_healthy=is_healthy,
            error_message=msg
        )

    async def save(self, job: dict[str, Any]) -> None:
        logger.info("LinkedInBrowserScraper discovered job: %s", job["title"])
