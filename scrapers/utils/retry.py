from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


async def retry_async(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    max_retries: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    recover_callback: Callable[[BaseException, str], Awaitable[None]] | None = None,
    label: str = "operation",
    **kwargs: Any,
) -> Any:
    attempt = 0
    while True:
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            attempt += 1
            logger.warning("Retry %s failed on attempt %s: %s", label, attempt, exc)
            if recover_callback:
                await recover_callback(exc, label)
            if attempt >= max_retries:
                logger.error("Max retries reached for %s", label)
                raise
            await asyncio.sleep(delay * (backoff ** (attempt - 1)))
