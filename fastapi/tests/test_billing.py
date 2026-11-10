import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.application.services.billing import (
    FREE_DAILY_SCRAPE_RUNS,
    FREE_MAX_DIGEST,
    FREE_SCRAPE_LIMIT,
    PLAN_FREE,
    PLAN_PRO,
    PRO_DAILY_SCRAPE_RUNS,
    PRO_MAX_DIGEST,
    PRO_SCRAPE_LIMIT,
    clamp_digest_limit,
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

    def test_market_entry_plan_limits(self) -> None:
        free = limits_for_user(_User())
        pro = limits_for_user(_User(plan=PLAN_PRO, subscription_status="active"))
        self.assertEqual(free.scrape_limit, FREE_SCRAPE_LIMIT)
        self.assertEqual(free.max_digest, FREE_MAX_DIGEST)
        self.assertEqual(free.daily_scrape_runs, FREE_DAILY_SCRAPE_RUNS)
        self.assertEqual(pro.scrape_limit, PRO_SCRAPE_LIMIT)
        self.assertEqual(pro.max_digest, PRO_MAX_DIGEST)
        self.assertEqual(pro.daily_scrape_runs, PRO_DAILY_SCRAPE_RUNS)
        self.assertIn("serpapi_freelance", free.allowed_sources)
        self.assertIn("serpapi_maps", pro.allowed_sources)
        self.assertNotIn("serpapi_maps", free.allowed_sources)
        self.assertTrue(any("digest" in f.lower() for f in free.features))
        self.assertFalse(any("bid bot" in f.lower() for f in pro.features))

    def test_clamp_digest_limit_respects_plan(self) -> None:
        free = _User()
        pro = _User(plan=PLAN_PRO, subscription_status="active")
        self.assertEqual(clamp_digest_limit(free, 50), FREE_MAX_DIGEST)
        self.assertEqual(clamp_digest_limit(free, 3), 3)
        self.assertEqual(clamp_digest_limit(pro, 50), PRO_MAX_DIGEST)
        self.assertEqual(clamp_digest_limit(pro, 10), 10)


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

    async def test_webhook_handles_invoice_payment_failed(self) -> None:
        from app.api.v1.billing import stripe_webhook

        settings = MagicMock()
        settings.stripe_enabled = True
        settings.stripe_webhook_secret = "whsec_test"
        request = MagicMock()
        request.body = AsyncMock(return_value=b'{"type": "invoice.payment_failed"}')
        request.headers = {"stripe-signature": "sig_test"}

        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "status": "past_due",
                }
            },
        }

        user = MagicMock()
        user.plan = "pro"
        user.subscription_status = "active"

        session = AsyncMock()
        session.add = MagicMock()
        user_res = MagicMock()
        user_res.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(return_value=user_res)

        with (
            patch("app.api.v1.billing.get_settings", return_value=settings),
            patch.dict("sys.modules", {"stripe": mock_stripe}),
        ):
            resp = await stripe_webhook(request=request, session=session)

        self.assertEqual(resp, {"status": "ok"})
        self.assertEqual(user.plan, "free")
        self.assertEqual(user.subscription_status, "past_due")

    async def test_webhook_handles_invoice_payment_succeeded_restores_pro(self) -> None:
        from app.api.v1.billing import stripe_webhook

        settings = MagicMock()
        settings.stripe_enabled = True
        settings.stripe_webhook_secret = "whsec_test"
        request = MagicMock()
        request.body = AsyncMock(return_value=b'{"type": "invoice.payment_succeeded"}')
        request.headers = {"stripe-signature": "sig_test"}

        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "status": "active",
                    "subscription": "sub_456",
                }
            },
        }

        user = MagicMock()
        user.plan = "free"
        user.subscription_status = "past_due"

        session = AsyncMock()
        session.add = MagicMock()
        user_res = MagicMock()
        user_res.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(return_value=user_res)

        with (
            patch("app.api.v1.billing.get_settings", return_value=settings),
            patch.dict("sys.modules", {"stripe": mock_stripe}),
        ):
            resp = await stripe_webhook(request=request, session=session)

        self.assertEqual(resp, {"status": "ok"})
        self.assertEqual(user.plan, "pro")
        self.assertEqual(user.subscription_status, "active")


if __name__ == "__main__":
    unittest.main()
