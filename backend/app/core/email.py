"""Outbound email helpers. Uses SMTP when configured; logs reset links in local/test."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core import secret_policy
from app.core.config import settings
from app.core.i18n import t
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


def send_password_reset_email(*, to_email: str, reset_url: str, locale: str | None = None) -> None:
    """Deliver a password-reset link. Logs the URL only in local/test without SMTP."""
    subject = t("auth.reset_subject", locale)
    body = t(
        "auth.reset_body",
        locale,
        minutes=settings.password_reset_expire_minutes,
        url=reset_url,
    )

    _send_or_log_email(
        to_email=to_email,
        subject=subject,
        body=body,
        log_label="password reset",
        log_url=reset_url,
    )


def send_verification_email(*, to_email: str, verify_url: str, locale: str | None = None) -> None:
    """Deliver an email-verification link. Logs the URL only in local/test without SMTP."""
    subject = t("auth.verify_subject", locale)
    body = t(
        "auth.verify_body",
        locale,
        hours=settings.email_verification_expire_minutes // 60,
        url=verify_url,
    )

    _send_or_log_email(
        to_email=to_email,
        subject=subject,
        body=body,
        log_label="email verification",
        log_url=verify_url,
    )


def send_existing_account_email(*, to_email: str, locale: str | None = None) -> None:
    """Tell an existing user someone tried to register with their address (AUT-27)."""
    base = settings.frontend_base_url.rstrip("/")
    login_url = f"{base}/login"
    forgot_url = f"{base}/forgot-password"
    subject = t("auth.existing_subject", locale)
    body = t(
        "auth.existing_body",
        locale,
        login_url=login_url,
        forgot_url=forgot_url,
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
