import asyncio
import unittest

from app.services.notification_service import NotificationChannel, NotificationPayload, NotificationPriority, NotificationService


class NotificationServiceTests(unittest.TestCase):
    def test_dispatch_returns_results_for_multiple_channels(self) -> None:
        service = NotificationService()
        payload = NotificationPayload(
            user_id="user-1",
            title="New job match",
            body="A matching freelance job is ready for review.",
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            priority=NotificationPriority.HIGH,
            ai_summary="A new job match was discovered.",
        )

        results = asyncio.run(service.dispatch(payload))

        self.assertEqual(len(results), 2)
        self.assertTrue(all(not result.delivered for result in results))
        self.assertTrue(all(result.error == "provider_not_configured" for result in results))

    def test_digest_mode_builds_summary(self) -> None:
        service = NotificationService()
        digest = service.build_digest([
            NotificationPayload(user_id="user-1", title="Job 1", body="First item", channels=[NotificationChannel.EMAIL]),
            NotificationPayload(user_id="user-1", title="Job 2", body="Second item", channels=[NotificationChannel.EMAIL]),
        ])

        self.assertTrue(digest.digest)
        self.assertIn("Daily digest", digest.title)
        self.assertIn("AI summary", digest.ai_summary or "")
