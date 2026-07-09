"""Outbound email helpers. Uses SMTP when configured; logs reset links in local/test."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core import secret_policy
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SmtpNotConfiguredError(RuntimeError):
    """Raised when SMTP is not configured but an email was requested."""


def send_email(*, to: str, subject: str, body: str, from_addr: str | None = None) -> None:
    """Deliver a plain-text email via SMTP."""
    if not settings.smtp_host:
        raise SmtpNotConfiguredError("SMTP is not configured (SMTP_HOST is unset)")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_addr or settings.smtp_from
    message["To"] = to
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)

    logger.info("Email sent to %s", to)


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    """Deliver a password-reset link. Logs the URL only in local/test without SMTP."""
    subject = "Reset your HeadStart password"
    body = (
        "You requested a password reset for your HeadStart account.\n\n"
        f"Open this link to choose a new password (valid for "
        f"{settings.password_reset_expire_minutes} minutes):\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    _send_or_log_email(
        to_email=to_email,
        subject=subject,
        body=body,
        log_label="password reset",
        log_url=reset_url,
    )


def send_verification_email(*, to_email: str, verify_url: str) -> None:
    """Deliver an email-verification link. Logs the URL only in local/test without SMTP."""
    subject = "Verify your HeadStart email"
    body = (
        "Thanks for creating a HeadStart account.\n\n"
        f"Open this link to verify your email address (valid for "
        f"{settings.email_verification_expire_minutes // 60} hours):\n\n"
        f"{verify_url}\n\n"
        "If you did not create this account, you can ignore this email."
    )

    _send_or_log_email(
        to_email=to_email,
        subject=subject,
        body=body,
        log_label="email verification",
        log_url=verify_url,
    )


def send_existing_account_email(*, to_email: str) -> None:
    """Tell an existing user someone tried to register with their address (AUT-27)."""
    base = settings.frontend_base_url.rstrip("/")
    login_url = f"{base}/login"
    forgot_url = f"{base}/forgot-password"
    subject = "Your HeadStart account"
    body = (
        "Someone tried to create a HeadStart account with this email address.\n\n"
        f"If that was you, sign in here:\n{login_url}\n\n"
        f"Forgot your password?\n{forgot_url}\n\n"
        "If you did not try to register, you can ignore this email."
    )

    _send_or_log_email(
        to_email=to_email,
        subject=subject,
        body=body,
        log_label="existing-account notice",
        log_url=login_url,
    )


def _send_or_log_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    log_label: str,
    log_url: str,
) -> None:
    try:
        send_email(to=to_email, subject=subject, body=body)
    except SmtpNotConfiguredError:
        # Never emit reset/verify tokens outside local/test (AUT-01). Startup
        # already requires SMTP_HOST in non-local envs; this is defense in depth.
        if not secret_policy.is_local_environment(settings.environment):
            logger.error(
                "SMTP not configured; refusing to log %s link for %s "
                "(ENVIRONMENT=%s is not local/test)",
                log_label,
                to_email,
                settings.environment,
            )
            raise
        logger.info(
            "SMTP not configured; %s link for %s: %s",
            log_label,
            to_email,
            log_url,
        )
