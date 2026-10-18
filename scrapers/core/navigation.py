from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Page


async def wait_for_element(page: Page, selector: str, timeout: int = 30) -> None:
    await page.wait_for_selector(selector, timeout=timeout * 1000)


async def infinite_scroll(
    page: Page, pause_time: float = 1.0, max_cycles: int = 20
) -> None:
    previous_height = await page.evaluate("() => document.body.scrollHeight")
    cycles = 0
    while cycles < max_cycles:
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(pause_time)
        current_height = await page.evaluate("() => document.body.scrollHeight")
        if current_height == previous_height:
            break
        previous_height = current_height
        cycles += 1


async def paginate(
    page: Page, next_button_selector: str, max_pages: int = 10, timeout: int = 30
) -> list[Any]:
    pages = []
    for _ in range(max_pages):
        await asyncio.sleep(1)
        pages.append(await page.content())
        next_button = await page.query_selector(next_button_selector)
        if not next_button:
            break
        await next_button.click()
        await page.wait_for_load_state("networkidle", timeout=timeout * 1000)
    return pages
