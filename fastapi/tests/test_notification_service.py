import asyncio
import unittest

from backend.application.services.notification_service import (
    NotificationChannel,
    NotificationPayload,
    NotificationPriority,
    NotificationService,
)


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
        self.assertTrue(
            all(result.error == "provider_not_configured" for result in results)
        )

    def test_digest_mode_builds_summary(self) -> None:
        service = NotificationService()
        digest = service.build_digest(
            [
                NotificationPayload(
                    user_id="user-1",
                    title="Job 1",
                    body="First item",
                    channels=[NotificationChannel.EMAIL],
                ),
                NotificationPayload(
                    user_id="user-1",
                    title="Job 2",
                    body="Second item",
                    channels=[NotificationChannel.EMAIL],
                ),
            ]
        )

        self.assertTrue(digest.digest)
        self.assertIn("Daily digest", digest.title)
        self.assertIn("AI summary", digest.ai_summary or "")

    def test_email_adapter_delivers_via_resend_httpx(self) -> None:
        from unittest.mock import MagicMock, patch

        service = NotificationService()
        payload = NotificationPayload(
            user_id="user-1",
            title="Signal Desk test alert",
            body="Outbound email test.",
            channels=[NotificationChannel.EMAIL],
            priority=NotificationPriority.NORMAL,
            destinations={"email": "user@example.com"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response

        with (
            patch.dict(
                "os.environ",
                {
                    "RESEND_API_KEY": "re_test_key",
                    "EMAIL_FROM": "Signal Desk <noreply@mail.faizanmalik.me>",
                },
                clear=False,
            ),
            patch(
                "httpx.Client",
                return_value=mock_client,
            ),
        ):
            results = asyncio.run(service.dispatch(payload))

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].delivered)
        self.assertIsNone(results[0].error)
