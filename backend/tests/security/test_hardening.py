"""Regression tests for the July 2026 security hardening changes."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.inbox_oauth_cookies import (
    MAILBOX_OAUTH_COOKIE_NAME,
    set_mailbox_oauth_nonce_cookie,
)
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.outbound_http import apply_outbound_pin
from app.core.outbound_url import UnsafeOutboundUrlError, pin_outbound_request
from app.core.security import (
    create_refresh_token,
    hash_password_reset_token,
)
from app.inbox.gmail_oauth import create_gmail_oauth_state
from app.inbox.mailbox_oauth_state import verify_mailbox_oauth_nonce
from app.models.base import utcnow
from app.models.inbox_classification import InboxClassification
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.resumes.latex_safety import reject_dangerous_latex_content
from app.resumes.template_bundle import parse_template_bundle
from app.schemas.auth import ResetPasswordRequest
from app.services.auth import AuthService
from app.services.feed import FeedService
from app.services.inbox_gate import auto_reply_recipient_allowed
from app.services.reply_safe_send import ReplySafeSendService
from tests.services.test_pending_replies import _seed_draft, _seed_mailbox
from tests.worker.test_pipeline import _make_search


def test_set_mailbox_oauth_nonce_cookie_sets_http_only_cookie() -> None:
    response = Response()
    set_mailbox_oauth_nonce_cookie(response, "nonce-value")
    cookie = response.headers.get("set-cookie", "")
    assert MAILBOX_OAUTH_COOKIE_NAME in cookie
    assert "nonce-value" in cookie
    assert "httponly" in cookie.lower()


def test_verify_mailbox_oauth_nonce_rejects_mismatch() -> None:
    with pytest.raises(Exception, match="OAuth session mismatch"):
        verify_mailbox_oauth_nonce("wrong", "expected")


def test_apply_outbound_pin_rewrites_resolved_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.outbound_http.pin_outbound_request",
        lambda url: type(
            "Pinned",
            (),
            {"request_url": "https://93.184.216.34/", "host_header": "example.com"},
        )(),
    )
    request = httpx.Request("GET", "https://example.com/path")
    apply_outbound_pin(request)
    assert str(request.url) == "https://93.184.216.34/"
    assert request.headers["Host"] == "example.com"
    assert request.extensions["sni_hostname"] == "example.com"


def test_pin_outbound_request_rejects_all_blocked_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    monkeypatch.setattr(
        "app.core.outbound_url.get_settings",
        lambda: type("S", (), {"environment": "production"})(),
    )

    AddrInfo = tuple[int, int, int, str, tuple[str, int]]

    def _loopback_only(*_args: object, **_kwargs: object) -> list[AddrInfo]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", _loopback_only)
    with pytest.raises(UnsafeOutboundUrlError, match="disallowed address"):
        pin_outbound_request("https://rebind.example.com/")


def test_reject_dangerous_latex_content_blocks_absolute_input() -> None:
    with pytest.raises(Exception, match="disallowed LaTeX commands"):
        reject_dangerous_latex_content("\\input{/etc/passwd}", label="evil.tex")


def test_parse_template_bundle_rejects_dangerous_tex_member() -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.tex", "\\input{/etc/passwd}")
    with pytest.raises(Exception, match="disallowed LaTeX commands"):
        parse_template_bundle(buffer.getvalue())


def test_auth_logout_ignores_invalid_refresh_token(db_session: Session) -> None:
    user = User(email="logout-bad@example.test", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    version_before = user.token_version
    AuthService(db_session).logout("not-a-valid-token")
    db_session.refresh(user)
    assert user.token_version == version_before


def test_parse_mailbox_oauth_state_rejects_missing_nonce() -> None:
    import jwt

    from app.inbox.mailbox_oauth_state import parse_mailbox_oauth_state

    token = jwt.encode(
        {"sub": "1", "type": "gmail_oauth", "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(Exception, match="Invalid or expired Gmail OAuth state"):
        parse_mailbox_oauth_state(
            state=token,
            state_type="gmail_oauth",
            error_message="Invalid or expired Gmail OAuth state.",
        )


def test_auto_reply_recipient_rejects_missing_employer_domain(db_session: Session) -> None:
    search = _make_search(db_session)
    draft = _seed_draft(db_session, search.user_id, search=search)
    assert draft.classification is not None
    assert draft.classification.seen_job_id is not None
    job = draft.classification.seen_job
    assert job is not None
    for log in job.application_logs:
        log.payload = {}
    job.url = "https://example.test/jobs/1"
    db_session.flush()
    assert (
        auto_reply_recipient_allowed(
            db_session,
            from_addr="hr@acme.com",
            classification=draft.classification,
        )
        is False
    )


def test_auth_logout_revokes_refresh_token(db_session: Session) -> None:
    user = User(email="logout@example.test", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    version_before = user.token_version
    refresh = create_refresh_token(user.id, version=user.token_version)
    AuthService(db_session).logout(refresh)
    db_session.refresh(user)
    assert user.token_version == version_before + 1


def test_auth_refresh_rotates_token_version(db_session: Session) -> None:
    user = User(email="rotate@example.test", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    old_refresh = create_refresh_token(user.id, version=user.token_version)
    AuthService(db_session).refresh(old_refresh)
    with pytest.raises(ValidationError, match="Session is no longer valid"):
        AuthService(db_session).refresh(old_refresh)


def test_password_reset_invalidates_feed_token(db_session: Session) -> None:
    user = User(email="feedreset@example.test", password_hash="x", is_active=True, plan="pro")
    db_session.add(user)
    db_session.flush()
    feed_token = FeedService(db_session).issue_token(user)
    raw = "reset-token-value"
    PasswordResetTokenRepository(db_session).add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw),
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    db_session.flush()
    AuthService(db_session).reset_password(
        ResetPasswordRequest(token=raw, password="new-password-12")
    )
    assert FeedService(db_session).resolve_user(feed_token) is None


def test_auto_reply_recipient_allowed_requires_linked_job(db_session: Session) -> None:
    classification = InboxClassification(
        user_id=1,
        message_uid=1,
        label="follow_up",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        from_addr="hr@acme.com",
    )
    allowed = auto_reply_recipient_allowed(
        db_session,
        from_addr="hr@acme.com",
        classification=classification,
    )
    assert allowed is False


def test_auto_reply_recipient_allowed_matches_employer_domain(db_session: Session) -> None:
    search = _make_search(db_session)
    draft = _seed_draft(db_session, search.user_id, search=search)
    assert draft.classification is not None
    assert auto_reply_recipient_allowed(
        db_session,
        from_addr="hr@acme.com",
        classification=draft.classification,
    )


def test_evaluate_before_send_blocks_mismatched_recipient(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    assert draft.classification is not None
    draft.classification.from_addr = "attacker@evil.com"
    decision = ReplySafeSendService(db_session).evaluate_before_send(
        user_id, draft, draft.classification
    )
    assert decision.allowed is False
    assert decision.outcome == "blocked_recipient"


def test_gmail_authorize_sets_oauth_nonce_cookie(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    resp = client.get("/api/v1/inbox/gmail/authorize", headers=auth_headers)
    assert resp.status_code == 200
    assert client.cookies.get(MAILBOX_OAUTH_COOKIE_NAME)


def test_gmail_callback_requires_matching_oauth_cookie(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    issued = create_gmail_oauth_state(1)
    resp = client.get(
        f"/api/v1/inbox/gmail/callback?code=c&state={issued.state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "gmail_error" in resp.headers["location"]


def test_outlook_authorize_sets_oauth_nonce_cookie(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "outlook_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "outlook_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "outlook_oauth_redirect_uri", "http://localhost/callback")
    resp = client.get("/api/v1/inbox/outlook/authorize", headers=auth_headers)
    assert resp.status_code == 200
    assert client.cookies.get(MAILBOX_OAUTH_COOKIE_NAME)


def test_yahoo_authorize_sets_oauth_nonce_cookie(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "http://localhost/callback")
    resp = client.get("/api/v1/inbox/yahoo/authorize", headers=auth_headers)
    assert resp.status_code == 200
    assert client.cookies.get(MAILBOX_OAUTH_COOKIE_NAME)


def test_auth_logout_noops_without_refresh_token(db_session: Session) -> None:
    user = User(email="logout-empty@example.test", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    version_before = user.token_version
    AuthService(db_session).logout(None)
    db_session.refresh(user)
    assert user.token_version == version_before


def test_auth_logout_noops_for_inactive_user(db_session: Session) -> None:
    user = User(email="logout-inactive@example.test", password_hash="x", is_active=False)
    db_session.add(user)
    db_session.flush()
    refresh = create_refresh_token(user.id, version=user.token_version)
    version_before = user.token_version
    AuthService(db_session).logout(refresh)
    db_session.refresh(user)
    assert user.token_version == version_before


def test_auth_logout_noops_when_token_version_stale(db_session: Session) -> None:
    user = User(email="logout-stale@example.test", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    stale_refresh = create_refresh_token(user.id, version=user.token_version - 1)
    version_before = user.token_version
    AuthService(db_session).logout(stale_refresh)
    db_session.refresh(user)
    assert user.token_version == version_before


def test_auto_reply_recipient_allowed_when_job_missing(db_session: Session) -> None:
    classification = InboxClassification(
        user_id=1,
        message_uid=1,
        label="follow_up",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        from_addr="hr@acme.com",
        seen_job_id=999_999,
    )
    allowed = auto_reply_recipient_allowed(
        db_session,
        from_addr="hr@acme.com",
        classification=classification,
    )
    assert allowed is False


def test_auto_reply_recipient_allowed_when_domain_unknown(db_session: Session) -> None:
    search = _make_search(db_session)
    draft = _seed_draft(db_session, search.user_id, search=search)
    assert draft.classification is not None
    assert draft.classification.seen_job_id is not None
    job = draft.classification.seen_job
    assert job is not None
    for log in job.application_logs:
        log.payload = {}
    job.url = "mailto:someone"
    db_session.flush()
    assert (
        auto_reply_recipient_allowed(
            db_session,
            from_addr="hr@acme.com",
            classification=draft.classification,
        )
        is False
    )


def test_parse_template_bundle_rejects_non_utf8_tex_member() -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.tex", b"\xff\xfe")
    with pytest.raises(Exception, match="must be valid UTF-8 text"):
        parse_template_bundle(buffer.getvalue())
