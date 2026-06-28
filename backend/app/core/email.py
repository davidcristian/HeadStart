"""Outbound email helpers. Uses SMTP when configured; logs reset links in dev."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    """Deliver a password-reset link. Falls back to logging when SMTP is not configured."""
    subject = "Reset your JobNotifier password"
    body = (
        "You requested a password reset for your JobNotifier account.\n\n"
        f"Open this link to choose a new password (valid for "
        f"{settings.password_reset_expire_minutes} minutes):\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    if not settings.smtp_host:
        logger.info(
            "SMTP not configured; password reset link for %s: %s",
            to_email,
            reset_url,
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)

    logger.info("Password reset email sent to %s", to_email)
