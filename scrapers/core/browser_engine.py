from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

DEFAULT_BLOCKED_RESOURCE_TYPES = ["image", "stylesheet", "font", "media"]
DEFAULT_STEALTH_SCRIPTS = [
    "() => { Object.defineProperty(navigator, 'webdriver', { get: () => false }); }",
    "() => { Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] }); }",
    "() => { Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] }); }",
]


def random_user_agent() -> str:
    browsers = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    ]
    return random.choice(browsers)


def random_viewport() -> dict[str, int]:
    widths = [1200, 1280, 1366, 1440, 1600]
    heights = [720, 800, 900, 1000]
    return {"width": random.choice(widths), "height": random.choice(heights)}


@dataclass
class BrowserSessionConfig:
    session_id: str
    storage_dir: Path
    headless: bool = True
    proxy: str | None = None
    user_agent: str | None = None
    block_resource_types: Iterable[str] = DEFAULT_BLOCKED_RESOURCE_TYPES
    stealth: bool = True
    timeout: int = 30
    viewport: dict[str, int] | None = None


class BrowserSession:
    def __init__(self, browser: Browser, config: BrowserSessionConfig) -> None:
        self.browser = browser
        self.config = config
        self.session_path = config.storage_dir / f"session_{config.session_id}.json"
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def initialize(self) -> None:
        context_args: dict[str, Any] = {
            "viewport": self.config.viewport or random_viewport(),
            "user_agent": self.config.user_agent or random_user_agent(),
            "java_script_enabled": True,
            "ignore_https_errors": True,
        }
        if self.config.proxy:
            context_args["proxy"] = {"server": self.config.proxy}
        if self.session_path.exists():
            context_args["storage_state"] = str(self.session_path)

        self.context = await self.browser.new_context(**context_args)

        if self.config.stealth:
            await self.apply_stealth()

        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.config.timeout * 1000)
        await self.install_resource_blocker(self.page)

    async def apply_stealth(self) -> None:
        if self.context is None:
            return
        for script in DEFAULT_STEALTH_SCRIPTS:
            await self.context.add_init_script(script=script)

    async def install_resource_blocker(self, page: Page) -> None:
        if self.context is None:
            return

        async def route_handler(route: Any) -> None:
            request = route.request
            if request.resource_type in set(self.config.block_resource_types):
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_handler)

    async def persist(self) -> None:
        if not self.context:
            return
        await self.context.storage_state(path=str(self.session_path))

    async def close(self) -> None:
        if self.context:
            await self.persist()
            await self.context.close()
        self.context = None
        self.page = None


class BrowserManager:
    def __init__(
        self,
        storage_dir: Path | str = Path("./.browser_sessions"),
        headless: bool = True,
        max_contexts: int = 4,
        proxy: str | None = None,
        block_resource_types: Iterable[str] = DEFAULT_BLOCKED_RESOURCE_TYPES,
        stealth: bool = True,
        timeout: int = 30,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.proxy = proxy
        self.max_contexts = max_contexts
        self.block_resource_types = block_resource_types
        self.stealth = stealth
        self.timeout = timeout
        self._playwright = None
        self.browser: Browser | None = None
        self._pool: asyncio.Queue[BrowserSession] = asyncio.Queue(max_contexts)
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(headless=self.headless)
            self._started = True
            logger.info("BrowserManager started with headless=%s", self.headless)

    async def stop(self) -> None:
        while not self._pool.empty():
            session = await self._pool.get()
            await session.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._started = False
        logger.info("BrowserManager stopped")

    async def acquire(self, session_id: str | None = None) -> BrowserSession:
        await self.start()
        try:
            session = self._pool.get_nowait()
            logger.debug("Reusing browser session %s", session.config.session_id)
            return session
        except asyncio.QueueEmpty:
            session_id = session_id or self._generate_session_id()
            return await self._create_session(session_id)

    async def release(self, session: BrowserSession) -> None:
        await session.persist()
        try:
            self._pool.put_nowait(session)
            logger.debug("Released browser session %s", session.config.session_id)
        except asyncio.QueueFull:
            await session.close()
            logger.debug("Closed browser session %s because pool was full", session.config.session_id)

    async def _create_session(self, session_id: str) -> BrowserSession:
        if self.browser is None:
            raise RuntimeError("BrowserManager not started")

        config = BrowserSessionConfig(
            session_id=session_id,
            storage_dir=self.storage_dir,
            headless=self.headless,
            proxy=self.proxy,
            block_resource_types=self.block_resource_types,
            stealth=self.stealth,
            timeout=self.timeout,
        )
        session = BrowserSession(browser=self.browser, config=config)
        await session.initialize()
        logger.info("Created browser session %s", session_id)
        return session

    @staticmethod
    def _generate_session_id(length: int = 16) -> str:
        return uuid.uuid4().hex[:length]
