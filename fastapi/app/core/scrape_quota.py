"""Daily per-user quota for manual /jobs/scrape runs (not Celery system hunts)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock

from fastapi import HTTPException, status

from backend.application.services.billing import PlanLimits


class DailyScrapeQuota:
    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)
        self._days: dict[str, str] = {}
        self._lock = Lock()

    @staticmethod
    def _utc_day() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _memory_key(self, user_id: str) -> str:
        return f"{user_id}:{self._utc_day()}"

    async def check_and_consume(self, user_id: str, limits: PlanLimits) -> int:
        """
        Increment the user's manual-scrape counter for the UTC day.
        Raises HTTP 402 when the plan daily_scrape_runs ceiling is exceeded.
        Returns the new count after consuming one run.
        """
        day = self._utc_day()
        redis_key = f"scrape_quota:{user_id}:{day}"
        limit = max(0, int(limits.daily_scrape_runs))

        from app.core.redis_client import get_redis

        client = await get_redis()
        if client:
            try:
                count = await client.incr(redis_key)
                if count == 1:
                    # Expire slightly after end of UTC day.
                    await client.expire(redis_key, 60 * 60 * 36)
                if count > limit:
                    await client.decr(redis_key)
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail={
                            "message": (
                                f"Daily manual hunt limit reached ({limit}/day on "
                                f"{limits.name} plan). Upgrade to Pro for higher density."
                            ),
                            "code": "daily_scrape_quota",
                            "limit": limit,
                            "used": limit,
                            "upgrade": "/pricing",
                        },
                    )
                return int(count)
            except HTTPException:
                raise
            except (OSError, RuntimeError, TimeoutError, ValueError):
                pass

        mem_key = self._memory_key(user_id)
        with self._lock:
            # Reset if calendar day rolled (process-local fallback).
            if self._days.get(user_id) != day:
                self._days[user_id] = day
                self._counts[mem_key] = 0
                # Drop stale keys for this user from prior days.
                for stale in [k for k in self._counts if k.startswith(f"{user_id}:") and k != mem_key]:
                    del self._counts[stale]
            if self._counts[mem_key] >= limit:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "message": (
                            f"Daily manual hunt limit reached ({limit}/day on "
                            f"{limits.name} plan). Upgrade to Pro for higher density."
                        ),
                        "code": "daily_scrape_quota",
                        "limit": limit,
                        "used": limit,
                        "upgrade": "/pricing",
                    },
                )
            self._counts[mem_key] += 1
            return self._counts[mem_key]

    async def remaining(self, user_id: str, limits: PlanLimits) -> int:
        day = self._utc_day()
        limit = max(0, int(limits.daily_scrape_runs))
        from app.core.redis_client import get_redis

        client = await get_redis()
        if client:
            raw = await client.get(f"scrape_quota:{user_id}:{day}")
            used = int(raw or 0)
            return max(0, limit - used)
        mem_key = self._memory_key(user_id)
        with self._lock:
            if self._days.get(user_id) != day:
                return limit
            return max(0, limit - self._counts.get(mem_key, 0))


daily_scrape_quota = DailyScrapeQuota()
