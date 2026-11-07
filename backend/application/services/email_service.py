from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.logging.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class EmailService:
    @staticmethod
    def _send(
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Sends transactional email via Resend HTTPS API if available, falling back to SMTP."""
        current_settings = get_settings()
        app_url = (getattr(current_settings, "public_app_url", None) or "http://localhost:3000").rstrip("/")
        default_headers = {
            "List-Unsubscribe": f"<{app_url}/preferences>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
        if headers:
            default_headers.update(headers)

        from_email = getattr(current_settings, "email_from", None) or "Signal Desk <notifications@signaldesk.com>"
        resend_key = getattr(current_settings, "resend_api_key", None)

        # 1. Prefer Resend HTTPS API (avoids cloud port 587/465 SMTP firewall restrictions)
        if resend_key:
            try:
                payload: dict[str, object] = {
                    "from": from_email,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                    "headers": default_headers,
                }
                if html_body:
                    payload["html"] = html_body

                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {resend_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if resp.status_code in (200, 201):
                        logger.info("Email sent via Resend to %s: %s", to_email, subject)
                        return True
                    logger.error(
                        "Resend API error (%s) delivering to %s: %s",
                        resp.status_code,
                        to_email,
                        resp.text,
                    )
            except Exception:
                logger.exception("Failed sending email via Resend to %s; falling back to SMTP if configured", to_email)

        # 2. SMTP fallback
        smtp_host = getattr(settings, "email_smtp_host", None)
        if not smtp_host:
            logger.warning(
                "Neither Resend nor SMTP configured; email not delivered to %s (%s)", to_email, subject
            )
            if not getattr(settings, "is_production", False):
                logger.info("DEV EMAIL PREVIEW %s for %s:\n%s", subject, to_email, body)
            # Never pretend delivery succeeded — callers rely on this for verify/reset.
            return False

        msg = MIMEMultipart("alternative")
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        for k, v in default_headers.items():
            msg[k] = v

        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        try:
            port = int(getattr(settings, "email_smtp_port", 587) or 587)
            smtp_user = getattr(settings, "email_username", None)
            smtp_pass = getattr(settings, "email_password", None)
            if port == 465:
                with smtplib.SMTP_SSL(smtp_host, port, timeout=10) as server:
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, port, timeout=10) as server:
                    server.starttls()
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
            logger.info("Email sent via SMTP to %s: %s", to_email, subject)
            return True
        except Exception:
            logger.exception("Failed to send email to %s: %s", to_email, subject)
            return False

    @staticmethod
    def send_password_reset_email(to_email: str, token: str) -> bool:
        app_url = (getattr(settings, "public_app_url", None) or "http://localhost:3000").rstrip("/")
        reset_link = f"{app_url}/auth/reset-password?token={token}"
        body = (
            "Hello,\n\n"
            "You have requested to reset your password. Open this link to set a new password:\n\n"
            f"{reset_link}\n\n"
            "If you did not request this, you can ignore this email.\n\n"
            "The Freelance Automation Team"
        )
        return EmailService._send(to_email, "Password Reset Request", body)

    @staticmethod
    def send_verification_email(to_email: str, token: str) -> bool:
        app_url = (getattr(settings, "public_app_url", None) or "http://localhost:3000").rstrip("/")
        verify_link = f"{app_url}/auth/verify?token={token}"
        body = (
            "Hello,\n\n"
            "Welcome to Freelance Intelligence. Confirm your email so we can send job alerts:\n\n"
            f"{verify_link}\n\n"
            "If you did not sign up, you can ignore this email.\n\n"
            "The Freelance Automation Team"
        )
        return EmailService._send(to_email, "Please verify your email address", body)

    @staticmethod
    def send_welcome_email(to_email: str, full_name: str | None = None) -> bool:
        name = full_name or "there"
        app_url = (getattr(settings, "public_app_url", None) or "http://localhost:3000").rstrip("/")
        prefs_link = f"{app_url}/preferences"
        body = (
            f"Hi {name},\n\n"
            "Your Signal Desk account is ready. Job alerts stay off until you verify your email.\n\n"
            f"Next, set the keywords you want us to watch: {prefs_link}\n\n"
            "The Signal Desk Team"
        )
        return EmailService._send(to_email, "Welcome to Signal Desk", body)

    @staticmethod
    def send_account_alert(to_email: str, subject: str, body: str) -> bool:
        return EmailService._send(to_email, subject, body)
