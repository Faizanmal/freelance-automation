import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.logging.logger import get_logger

from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class EmailService:
    @staticmethod
    def _send(to_email: str, subject: str, body: str) -> bool:
        if not settings.email_smtp_host:
            logger.warning(
                "SMTP not configured; email not delivered to %s (%s)", to_email, subject
            )
            if not settings.is_production:
                logger.info("DEV EMAIL PREVIEW %s for %s:\n%s", subject, to_email, body)
            # Never pretend delivery succeeded — callers rely on this for verify/reset.
            return False

        msg = MIMEMultipart()
        msg["From"] = settings.email_from or "noreply@freelance-automation.com"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(
                settings.email_smtp_host, settings.email_smtp_port, timeout=8
            ) as server:
                server.starttls()
                if settings.email_username and settings.email_password:
                    server.login(settings.email_username, settings.email_password)
                server.send_message(msg)
            logger.info("Email sent to %s: %s", to_email, subject)
            return True
        except Exception:
            logger.exception("Failed to send email to %s: %s", to_email, subject)
            return False

    @staticmethod
    def send_password_reset_email(to_email: str, token: str) -> bool:
        reset_link = f"{settings.public_app_url}/auth/reset-password?token={token}"
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
        verify_link = f"{settings.public_app_url}/auth/verify?token={token}"
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
        prefs_link = f"{settings.public_app_url}/preferences"
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
