"""Tests for structured auth security event logging (AUT-10)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core import metrics
from app.core.auth_events import log_auth_event
from app.core.security import (
    create_refresh_token,
    hash_password,
    pseudonymize_email_for_audit,
)
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import (
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
)
from app.services.auth import AuthService


@pytest.fixture
def metrics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics, "get_settings", lambda: SimpleNamespace(metrics_enabled=True))


def _user(db_session: Session, *, email: str = "events@example.com") -> User:
    return UserRepository(db_session).add(
        User(email=email, password_hash=hash_password("password123"), is_active=True)
    )


def test_log_auth_event_omits_plaintext_email(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="app.core.auth_events"):
        log_auth_event(
            "login_success",
            email="secret@example.com",
            user_id=7,
            ip_address="203.0.113.9",
        )
    assert len(caplog.records) == 1
    record = caplog.records[0]
    message = record.getMessage()
    assert "secret@example.com" not in message
    email_hash = pseudonymize_email_for_audit("secret@example.com")
    assert f"email_hash={email_hash}" in message
    assert "auth_event=login_success" in message
    assert "user_id=7" in message
    assert "ip=203.0.113.9" in message
    assert record.auth_event == "login_success"
    assert record.email_hash == email_hash
    assert record.user_id == 7
    assert record.ip == "203.0.113.9"


def test_log_auth_event_without_email(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="app.core.auth_events"):
        log_auth_event("session_invalidated", user_id=3, reason="logout")
    record = caplog.records[0]
    message = record.getMessage()
    assert "email_hash=" not in message
    assert "user_id=3" in message
    assert "reason=logout" in message
    assert record.auth_event == "session_invalidated"
    assert record.user_id == 3
    assert record.reason == "logout"
    assert not hasattr(record, "email_hash")
    assert not hasattr(record, "issued")


def test_login_failure_logs_and_increments_metric(
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    metrics_enabled: None,
) -> None:
    before = metrics.AUTH_LOGIN_FAILURES._value.get()  # type: ignore[attr-defined]
    with (
        caplog.at_level("INFO", logger="app.core.auth_events"),
        pytest.raises(Exception, match="Invalid email or password"),
    ):
        AuthService(db_session).login(
            LoginRequest(email="missing@example.com", password="wrong"),
            ip_address="198.51.100.1",
        )
    assert any("auth_event=login_failure" in r.getMessage() for r in caplog.records)
    assert any("email_hash=" in r.getMessage() for r in caplog.records)
    assert any("ip=198.51.100.1" in r.getMessage() for r in caplog.records)
    after = metrics.AUTH_LOGIN_FAILURES._value.get()  # type: ignore[attr-defined]
    assert after == before + 1


def test_login_success_logs_event(db_session: Session, caplog: pytest.LogCaptureFixture) -> None:
    user = _user(db_session)
    with caplog.at_level("INFO", logger="app.core.auth_events"):
        AuthService(db_session).login(
            LoginRequest(email=user.email, password="password123"),
            ip_address="198.51.100.2",
        )
    assert any("auth_event=login_success" in r.getMessage() for r in caplog.records)
    assert any(f"user_id={user.id}" in r.getMessage() for r in caplog.records)


def test_inactive_login_logs_failure(
    db_session: Session, caplog: pytest.LogCaptureFixture, metrics_enabled: None
) -> None:
    user = _user(db_session, email="inactive-events@example.com")
    user.is_active = False
    db_session.flush()
    before = metrics.AUTH_LOGIN_FAILURES._value.get()  # type: ignore[attr-defined]
    with (
        caplog.at_level("INFO", logger="app.core.auth_events"),
        pytest.raises(Exception, match="Invalid email or password"),
    ):
        AuthService(db_session).login(
            LoginRequest(email=user.email, password="password123"),
            ip_address="198.51.100.3",
        )
    assert any("auth_event=login_failure" in r.getMessage() for r in caplog.records)
    after = metrics.AUTH_LOGIN_FAILURES._value.get()  # type: ignore[attr-defined]
    assert after == before + 1


def test_password_reset_requested_and_completed_log(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    user = _user(db_session, email="reset-events@example.com")
    with (
        patch("app.services.auth_password.send_password_reset_email"),
        patch(
            "app.services.auth_password.generate_password_reset_token",
            return_value="reset-raw",
        ),
        caplog.at_level("INFO", logger="app.core.auth_events"),
    ):
        AuthService(db_session).request_password_reset(
            ForgotPasswordRequest(email=user.email),
            ip_address="198.51.100.4",
        )
    assert any("auth_event=password_reset_requested" in r.getMessage() for r in caplog.records)
    assert any("issued=true" in r.getMessage() for r in caplog.records)

    caplog.clear()
    with caplog.at_level("INFO", logger="app.core.auth_events"):
        AuthService(db_session).reset_password(
            ResetPasswordRequest(token="reset-raw", password="brand-new-pass"),
            ip_address="198.51.100.5",
        )
    messages = [r.getMessage() for r in caplog.records]
    assert any("auth_event=password_reset_completed" in m for m in messages)
    assert any(
        "auth_event=session_invalidated" in m and "reason=password_reset" in m for m in messages
    )


def test_password_reset_missing_account_logs_not_issued(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="app.core.auth_events"):
        AuthService(db_session).request_password_reset(
            ForgotPasswordRequest(email="nobody@example.com"),
            ip_address="198.51.100.6",
        )
    assert any("auth_event=password_reset_requested" in r.getMessage() for r in caplog.records)
    assert any("issued=false" in r.getMessage() for r in caplog.records)


def test_logout_logs_session_invalidated(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    user = _user(db_session, email="logout-events@example.com")
    refresh = create_refresh_token(user.id, version=user.token_version)
    with caplog.at_level("INFO", logger="app.core.auth_events"):
        AuthService(db_session).logout(refresh, ip_address="198.51.100.7")
    assert any(
        "auth_event=session_invalidated" in r.getMessage() and "reason=logout" in r.getMessage()
        for r in caplog.records
    )


def test_account_deletion_logs_event(db_session: Session, caplog: pytest.LogCaptureFixture) -> None:
    user = _user(db_session, email="delete-events@example.com")
    with (
        patch("app.services.auth_account.release_stripe_billing"),
        caplog.at_level("INFO", logger="app.core.auth_events"),
    ):
        AuthService(db_session).delete_account(
            user.id,
            DeleteAccountRequest(password="password123"),
            ip_address="198.51.100.8",
        )
    assert any("auth_event=account_deleted" in r.getMessage() for r in caplog.records)
    assert any("email_hash=" in r.getMessage() for r in caplog.records)
    assert UserRepository(db_session).get_by_email("delete-events@example.com") is None
