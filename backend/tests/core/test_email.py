"""Tests for outbound email helpers (SMTP delivery + dev logging fallback)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core import email as email_module
from app.core.config import settings
from app.core.email import (
    SmtpNotConfiguredError,
    send_email,
    send_password_reset_email,
    send_verification_email,
)


def test_send_email_raises_when_smtp_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")
    with pytest.raises(SmtpNotConfiguredError):
        send_email(to="a@example.com", subject="Hi", body="Body")


def test_send_email_delivers_via_smtp_with_auth_and_tls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr(settings, "smtp_user", "mailer")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")

    smtp_instance = MagicMock()
    smtp_cm = MagicMock()
    smtp_cm.__enter__.return_value = smtp_instance
    with patch.object(email_module.smtplib, "SMTP", return_value=smtp_cm) as mock_smtp:
        send_email(to="user@example.com", subject="Subject", body="Body")

    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("mailer", "secret")
    smtp_instance.send_message.assert_called_once()
    sent = smtp_instance.send_message.call_args.args[0]
    assert sent["To"] == "user@example.com"
    assert sent["From"] == "noreply@example.com"
    assert sent["Subject"] == "Subject"


def test_send_email_without_tls_or_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    monkeypatch.setattr(settings, "smtp_user", "")

    smtp_instance = MagicMock()
    smtp_cm = MagicMock()
    smtp_cm.__enter__.return_value = smtp_instance
    with patch.object(email_module.smtplib, "SMTP", return_value=smtp_cm):
        send_email(to="user@example.com", subject="S", body="B", from_addr="custom@example.com")

    smtp_instance.starttls.assert_not_called()
    smtp_instance.login.assert_not_called()
    sent = smtp_instance.send_message.call_args.args[0]
    assert sent["From"] == "custom@example.com"


def test_send_password_reset_email_uses_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch.object(email_module, "send_email") as mock_send:
        send_password_reset_email(to_email="user@example.com", reset_url="https://app/reset?x=1")
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "user@example.com"
    assert "https://app/reset?x=1" in kwargs["body"]


def test_send_verification_email_uses_smtp() -> None:
    with patch.object(email_module, "send_email") as mock_send:
        send_verification_email(to_email="user@example.com", verify_url="https://app/verify?x=1")
    kwargs = mock_send.call_args.kwargs
    assert "https://app/verify?x=1" in kwargs["body"]


def test_send_or_log_email_falls_back_to_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SMTP is unconfigured the link is logged instead of raising."""
    monkeypatch.setattr(settings, "smtp_host", "")
    with patch.object(email_module.logger, "info") as mock_log:
        send_password_reset_email(to_email="user@example.com", reset_url="https://app/reset")
    assert any("password reset" in str(call.args) for call in mock_log.call_args_list)
