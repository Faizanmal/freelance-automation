import logging
from abc import ABC, abstractmethod
from typing import Any

from scrapers.core.interfaces import IScraper

logger = logging.getLogger(__name__)

class BaseApiScraper(IScraper, ABC):
    """Base scraper for API-only sources (no browser dependencies)."""

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit
        self.jobs: list[dict[str, Any]] = []

    async def login(self) -> None:
        """API scrapers generally don't require an explicit login step."""

    async def save(self, job: dict[str, Any]) -> None:
        """For testing/standalone usage, this can be overridden."""
        self.jobs.append(job)
        logger.debug("Saved job %s in memory", job.get("external_id"))

    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> None:
        """Perform the API request."""
        raise NotImplementedError

    @abstractmethod
    async def extract_jobs(self) -> list[dict[str, Any]]:
        """Extract the raw job dicts from the API response."""
        raise NotImplementedError

    @abstractmethod
    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw API response row to the standard schema."""
        raise NotImplementedError
