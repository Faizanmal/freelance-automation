from __future__ import annotations

import asyncio
from time import monotonic


class RateLimiter:
    def __init__(self, rate_per_second: int = 1) -> None:
        self.rate_per_second = rate_per_second
        self._last_called = 0.0

    async def wait(self) -> None:
        if self.rate_per_second <= 0:
            return

        elapsed = monotonic() - self._last_called
        wait_for = max(0.0, 1.0 / self.rate_per_second - elapsed)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        self._last_called = monotonic()
