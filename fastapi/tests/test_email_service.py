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


if __name__ == "__main__":
    unittest.main()
