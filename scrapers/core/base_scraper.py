from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Self

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from scrapers.core.browser_use import BrowserUse
from scrapers.core.errors import SelectorFallbackError
from scrapers.core.interfaces import IScraper
from scrapers.core.selector_store import ISelectorStore, MemorySelectorStore
from scrapers.utils.rate_limit import RateLimiter
from scrapers.utils.retry import retry_async

logger = logging.getLogger(__name__)


class BaseScraper(IScraper, ABC):
    def __init__(
        self,
        base_url: str,
        storage_dir: Path | str,
        proxy: str | None = None,
        max_retries: int = 3,
        rate_limit: int = 1,
        timeout: int = 30,
        selector_store: ISelectorStore | None = None,
        fallback_selectors: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.storage_dir = Path(storage_dir)
        self.proxy = proxy
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(rate_limit)
        self.timeout = timeout
        self.selector_store = selector_store or MemorySelectorStore()
        self.fallback_selectors = fallback_selectors or {}
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> Self:
        await self.launch_browser()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close_browser()

    async def launch_browser(self) -> None:
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        context_args: dict[str, Any] = {
            "viewport": {"width": 1280, "height": 800},
            "java_script_enabled": True,
            "ignore_https_errors": True,
        }
        if self.proxy:
            context_args["proxy"] = {"server": self.proxy}

        self.context = await self.browser.new_context(**context_args)
        await self.load_cookies()
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout * 1000)

    async def close_browser(self) -> None:
        if self.context:
            await self.save_cookies()
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def load_cookies(self) -> None:
        cookie_path = self.storage_dir / "cookies.json"
        if cookie_path.exists() and self.context:
            text = cookie_path.read_text(encoding="utf-8")
            try:
                cookies = json.loads(text)
                await self.context.add_cookies(cookies)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load cookies: %s", exc)

    async def save_cookies(self) -> None:
        if self.context:
            cookie_path = self.storage_dir / "cookies.json"
            cookies = await self.context.cookies()
            cookie_path.write_text(json.dumps(cookies), encoding="utf-8")

    async def capture_screenshot(self, label: str) -> None:
        if self.page:
            screenshot_path = self.storage_dir / f"failure_{label}.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            logger.debug("Saved failure screenshot to %s", screenshot_path)

    async def _execute_with_retries(self, coro: Any, *args: Any, **kwargs: Any) -> Any:
        return await retry_async(
            coro,
            *args,
            max_retries=self.max_retries,
            recover_callback=self._handle_failure,
            **kwargs,
        )

    async def _handle_failure(self, exc: BaseException, label: str) -> None:
        logger.warning("Handling failure for %s: %s", label, exc)
        await self.capture_screenshot(label)

    async def run(self, query: str, **kwargs: Any) -> None:
        logger.info("Running scraper for %s", query)
        await self.launch_browser()
        try:
            await self.login()
            await self.rate_limiter.wait()
            await self.search(query, **kwargs)
            raw_jobs = await self.extract_jobs()
            for raw_job in raw_jobs:
                normalized = await self.normalize(raw_job)
                await self.save(normalized)
        except SelectorFallbackError as exc:
            logger.warning("Selector fallback triggered: %s", exc)
            await self._recover_with_browser_use(exc.field_name, exc.current_selector, exc.candidates, query, **kwargs)
        finally:
            await self.close_browser()

    async def _recover_with_browser_use(
        self,
        field_name: str,
        current_selector: str,
        candidates: list[str],
        query: str,
        **kwargs: Any,
    ) -> None:
        if not self.page:
            raise RuntimeError("Page is not available for Browser Use recovery")

        browser_use = BrowserUse(
            page=self.page,
            selector_store=self.selector_store,
            fallback_selectors=self.fallback_selectors,
        )
        next_selector = await browser_use.verify_and_recover(field_name, current_selector, candidates)
        if not next_selector:
            raise RuntimeError(f"Unable to recover selector for {field_name}")

        self.update_selector_config(field_name, next_selector)
        await self.search(query, **kwargs)
        raw_jobs = await self.extract_jobs()
        for raw_job in raw_jobs:
            normalized = await self.normalize(raw_job)
            await self.save(normalized)

    def update_selector_config(self, field_name: str, selector: str) -> None:
        logger.info("Updating selector config for %s", field_name)
        setattr(self, f"{field_name}_selector", selector)

    @abstractmethod
    async def login(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    async def extract_jobs(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def normalize(self, raw_job: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def save(self, job: dict[str, Any]) -> None:
        raise NotImplementedError
