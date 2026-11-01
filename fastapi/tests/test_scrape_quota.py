import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.scrape_quota import DailyScrapeQuota
from backend.application.services.billing import PLAN_FREE, PLAN_PRO, PLANS


class DailyScrapeQuotaTests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_fallback_enforces_free_daily_cap(self) -> None:
        quota = DailyScrapeQuota()
        limits = PLANS[PLAN_FREE]
        with patch("app.core.redis_client.get_redis", new=AsyncMock(return_value=None)):
            for _ in range(limits.daily_scrape_runs):
                await quota.check_and_consume("user-free", limits)
            with self.assertRaises(HTTPException) as ctx:
                await quota.check_and_consume("user-free", limits)
        self.assertEqual(ctx.exception.status_code, 402)
        detail = ctx.exception.detail
        self.assertIsInstance(detail, dict)
        self.assertEqual(detail["code"], "daily_scrape_quota")

    async def test_pro_daily_cap_is_higher(self) -> None:
        quota = DailyScrapeQuota()
        free = PLANS[PLAN_FREE]
        pro = PLANS[PLAN_PRO]
        self.assertGreater(pro.daily_scrape_runs, free.daily_scrape_runs)
        with patch("app.core.redis_client.get_redis", new=AsyncMock(return_value=None)):
            for _ in range(free.daily_scrape_runs + 1):
                count = await quota.check_and_consume("user-pro", pro)
            self.assertEqual(count, free.daily_scrape_runs + 1)
            remaining = await quota.remaining("user-pro", pro)
        self.assertEqual(remaining, pro.daily_scrape_runs - (free.daily_scrape_runs + 1))


if __name__ == "__main__":
    unittest.main()
