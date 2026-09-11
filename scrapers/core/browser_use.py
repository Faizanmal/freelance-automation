from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from playwright.async_api import Page

from scrapers.core.selector_store import ISelectorStore
from scrapers.core.helpers import is_captcha_page
from scrapers.core.navigation import wait_for_element

logger = logging.getLogger(__name__)


class IBrowserUse(ABC):
    @abstractmethod
    async def navigate(self, url: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def resolve_selector(self, field_name: str, candidates: list[str]) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def verify_and_recover(self, field_name: str, current_selector: str, candidates: list[str]) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def should_fallback(self) -> bool:
        raise NotImplementedError


class BrowserUse(IBrowserUse):
    def __init__(
        self,
        page: Page,
        selector_store: ISelectorStore,
        fallback_selectors: dict[str, str] | None = None,
    ) -> None:
        self.page = page
        self.selector_store = selector_store
        self.fallback_selectors = fallback_selectors or {}

    async def navigate(self, url: str) -> None:
        await self.page.goto(url)
        await self.page.wait_for_load_state("networkidle")

    async def identify_selector(self, field_name: str, candidates: list[str]) -> str | None:
        for selector in candidates:
            try:
                await wait_for_element(self.page, selector, timeout=5)
                logger.info("Selector identified for %s: %s", field_name, selector)
                await self.selector_store.save_selector(field_name, selector)
                return selector
            except Exception:
                continue
        return None

    async def resolve_selector(self, field_name: str, candidates: list[str]) -> str | None:
        persisted = await self.selector_store.get_selector(field_name)
        if persisted:
            try:
                await wait_for_element(self.page, persisted, timeout=5)
                return persisted
            except Exception:
                logger.info("Persisted selector failed for %s: %s", field_name, persisted)

        if self.fallback_selectors.get(field_name):
            candidates.insert(0, self.fallback_selectors[field_name])

        return await self.identify_selector(field_name, candidates)

    async def verify_and_recover(self, field_name: str, current_selector: str, candidates: list[str]) -> str | None:
        try:
            await wait_for_element(self.page, current_selector, timeout=5)
            return current_selector
        except Exception:
            logger.warning("Primary selector failed for %s: %s", field_name, current_selector)
            return await self.resolve_selector(field_name, candidates)

    async def should_fallback(self) -> bool:
        return await is_captcha_page(self.page)
