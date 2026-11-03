"""Remaining: SMTP honesty — never fake success when host is unset."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.application.services.email_service import EmailService


class EmailServiceTests(unittest.TestCase):
    def test_missing_smtp_returns_false_in_dev(self) -> None:
        settings = SimpleNamespace(
            email_smtp_host=None,
            is_production=False,
            email_from=None,
            email_smtp_port=587,
            email_username=None,
            email_password=None,
        )
        with patch("backend.application.services.email_service.settings", settings):
            self.assertFalse(EmailService._send("a@b.c", "Subject", "Body"))

    def test_missing_smtp_returns_false_in_production(self) -> None:
        settings = SimpleNamespace(
            email_smtp_host=None,
            is_production=True,
            email_from=None,
            email_smtp_port=587,
            email_username=None,
            email_password=None,
        )
        with patch("backend.application.services.email_service.settings", settings):
            self.assertFalse(EmailService._send("a@b.c", "Subject", "Body"))

    def test_smtp_send_success(self) -> None:
        settings = SimpleNamespace(
            email_smtp_host="smtp.test",
            email_smtp_port=587,
            email_username="user",
            email_password="pass",
            email_from="from@test.com",
            is_production=False,
        )
        smtp = MagicMock()
        smtp.__enter__ = MagicMock(return_value=smtp)
        smtp.__exit__ = MagicMock(return_value=False)
        with (
            patch("backend.application.services.email_service.settings", settings),
            patch(
                "backend.application.services.email_service.smtplib.SMTP",
                return_value=smtp,
            ),
        ):
            self.assertTrue(EmailService._send("a@b.c", "Subject", "Body"))
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("user", "pass")
        smtp.send_message.assert_called_once()

    def test_resend_send_success(self) -> None:
        settings = SimpleNamespace(
            resend_api_key="re_secret_123",
            email_smtp_host=None,
            email_from="notifications@signaldesk.com",
            public_app_url="https://signaldesk.com",
            is_production=True,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with (
            patch("backend.application.services.email_service.settings", settings),
            patch("backend.application.services.email_service.httpx.Client", return_value=mock_client),
        ):
            ok = EmailService._send("lead@example.com", "New Opportunity", "Check this job out")
            self.assertTrue(ok)

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args.kwargs
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer re_secret_123")
        self.assertEqual(call_kwargs["json"]["to"], ["lead@example.com"])
        self.assertIn("List-Unsubscribe", call_kwargs["json"]["headers"])

    def test_resend_error_falls_back_to_smtp(self) -> None:
        settings = SimpleNamespace(
            resend_api_key="re_failing_key",
            email_smtp_host="smtp.test",
            email_smtp_port=587,
            email_username="user",
            email_password="pass",
            email_from="from@test.com",
            is_production=True,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        smtp = MagicMock()
        smtp.__enter__ = MagicMock(return_value=smtp)
        smtp.__exit__ = MagicMock(return_value=False)

        with (
            patch("backend.application.services.email_service.settings", settings),
            patch("backend.application.services.email_service.httpx.Client", return_value=mock_client),
            patch("backend.application.services.email_service.smtplib.SMTP", return_value=smtp),
        ):
            ok = EmailService._send("lead@example.com", "Title", "Body")
            self.assertTrue(ok)

        smtp.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
