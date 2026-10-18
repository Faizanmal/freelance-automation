import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.application.services.billing import (
    PLAN_FREE,
    PLAN_PRO,
    filter_channels_for_user,
    filter_sources_for_user,
    is_pro,
    limits_for_user,
)


class _User:
    def __init__(
        self, plan: str = "free", subscription_status: str = "inactive"
    ) -> None:
        self.plan = plan
        self.subscription_status = subscription_status


class BillingServiceTests(unittest.TestCase):
    def test_free_plan_blocks_marketplace_sources(self) -> None:
        user = _User()
        sources = filter_sources_for_user(user, ["remoteok", "upwork", "freelancer"])
        self.assertEqual(sources, ["remoteok"])
        self.assertFalse(limits_for_user(user).marketplace)

    def test_pro_plan_allows_marketplace_and_channels(self) -> None:
        user = _User(plan=PLAN_PRO, subscription_status="active")
        self.assertTrue(is_pro(user))
        sources = filter_sources_for_user(
            user, ["remoteok", "upwork", "serpapi_freelance", "remotive"]
        )
        self.assertEqual(sources, ["remoteok", "upwork", "serpapi_freelance"])
        channels = filter_channels_for_user(user, ["email", "slack", "carrier-pigeon"])
        self.assertEqual(channels, ["email", "slack"])
        self.assertEqual(limits_for_user(user).price_label, "$19/mo")
        self.assertIn("serpapi_jobs", limits_for_user(user).allowed_sources)

    def test_restricted_sources_are_not_in_commercial_plans(self) -> None:
        free = limits_for_user(_User())
        pro = limits_for_user(_User(plan=PLAN_PRO, subscription_status="active"))
        self.assertNotIn("remotive", free.allowed_sources)
        self.assertNotIn("weworkremotely", free.allowed_sources)
        self.assertNotIn("remotive", pro.allowed_sources)
        self.assertNotIn("peopleperhour", pro.allowed_sources)

    def test_inactive_pro_falls_back_to_free(self) -> None:
        user = _User(plan=PLAN_PRO, subscription_status="canceled")
        self.assertFalse(is_pro(user))
        self.assertEqual(limits_for_user(user).name, PLAN_FREE)

    def test_past_due_is_not_pro(self) -> None:
        user = _User(plan=PLAN_PRO, subscription_status="past_due")
        self.assertFalse(is_pro(user))
        self.assertEqual(limits_for_user(user).name, PLAN_FREE)


class StripeWebhookGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_webhook_rejects_missing_secret(self) -> None:
        from app.api.v1.billing import stripe_webhook

        from fastapi import HTTPException

        settings = MagicMock()
        settings.stripe_enabled = True
        settings.stripe_webhook_secret = None
        request = MagicMock()
        request.body = AsyncMock(return_value=b"{}")
        request.headers = {}

        with (
            patch("app.api.v1.billing.get_settings", return_value=settings),
            patch.dict("sys.modules", {"stripe": MagicMock()}),
            self.assertRaises(HTTPException) as ctx,
        ):
            await stripe_webhook(request=request, session=AsyncMock())

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("STRIPE_WEBHOOK_SECRET", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
