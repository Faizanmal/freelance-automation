from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page


async def save_failure_screenshot(page: Page, storage_dir: Path, name: str) -> None:
    path = storage_dir / f"failure_{name}.png"
    await page.screenshot(path=str(path), full_page=True)


async def is_captcha_page(page: Page) -> bool:
    content = await page.content()
    return "captcha" in content.lower() or "recaptcha" in content.lower()


def build_cookie_path(storage_dir: Path, session_id: str) -> Path:
    return storage_dir / f"cookies_{session_id}.json"
