import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import get_settings
from app.core.logging.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

class EmailService:
    @staticmethod
    def send_password_reset_email(to_email: str, token: str) -> bool:
        if not settings.email_smtp_host:
            logger.warning("SMTP not configured, falling back to console log for %s", to_email)
            logger.info("PASSWORD RESET LINK FOR %s: %s/reset-password?token=%s", to_email, settings.public_app_url, token)
            return True
            
        reset_link = f"{settings.public_app_url}/reset-password?token={token}"
        
        msg = MIMEMultipart()
        msg['From'] = settings.email_from or "noreply@freelance-automation.com"
        msg['To'] = to_email
        msg['Subject'] = "Password Reset Request"
        
        body = f"""
Hello,

You have requested to reset your password. Please click the link below to set a new password:

{reset_link}

If you did not request this, please ignore this email.

Best,
The Freelance Automation Team
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as server:
                server.starttls()
                if settings.email_username and settings.email_password:
                    server.login(settings.email_username, settings.email_password)
                server.send_message(msg)
                
            logger.info("Password reset email sent successfully to %s", to_email)
            return True
        except Exception as e:
            logger.exception("Failed to send password reset email to %s", to_email)
            return False

    @staticmethod
    def send_verification_email(to_email: str, token: str) -> bool:
        if not settings.email_smtp_host:
            logger.warning("SMTP not configured, falling back to console log for %s", to_email)
            logger.info("EMAIL VERIFICATION LINK FOR %s: %s/verify-email?token=%s", to_email, settings.public_app_url, token)
            return True
            
        verify_link = f"{settings.public_app_url}/verify-email?token={token}"
        
        msg = MIMEMultipart()
        msg['From'] = settings.email_from or "noreply@freelance-automation.com"
        msg['To'] = to_email
        msg['Subject'] = "Please verify your email address"
        
        body = f"""
Hello,

Welcome to Freelance Intelligence! Please click the link below to verify your email address:

{verify_link}

If you did not sign up for an account, please ignore this email.

Best,
The Freelance Automation Team
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as server:
                server.starttls()
                if settings.email_username and settings.email_password:
                    server.login(settings.email_username, settings.email_password)
                server.send_message(msg)
                
            logger.info("Verification email sent successfully to %s", to_email)
            return True
        except Exception as e:
            logger.exception("Failed to send verification email to %s", to_email)
            return False
