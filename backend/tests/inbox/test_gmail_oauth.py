"""Tests for Gmail OAuth helpers (mocked HTTP)."""

import jwt
import pytest
import respx
from httpx import Response

from app.core.config import settings
from app.inbox.gmail_oauth import (
    GmailOAuthError,
    build_gmail_authorization_url,
    create_gmail_oauth_state,
    decode_gmail_oauth_state,
    exchange_gmail_code,
    gmail_oauth_configured,
    revoke_gmail_tokens,
)
from app.inbox.types import GmailMailboxConfig


def test_gmail_oauth_configured_requires_all_vars(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "")
    assert gmail_oauth_configured() is False

    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    assert gmail_oauth_configured() is True


def test_gmail_oauth_state_round_trip() -> None:
    issued = create_gmail_oauth_state(42)
    assert decode_gmail_oauth_state(issued.state) == (42, issued.nonce, issued.code_verifier)


def test_build_authorization_url_contains_client_id_and_pkce(monkeypatch) -> None:
    from app.inbox.mailbox_oauth_state import code_challenge_s256

    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    url = build_gmail_authorization_url(state="signed-state", code_verifier="verifier-value")
    assert "client_id=client-id" in url
    assert "state=signed-state" in url
    assert "code_challenge_method=S256" in url
    assert f"code_challenge={code_challenge_s256('verifier-value')}" in url


@respx.mock
def test_exchange_gmail_code_returns_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    route = respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    )
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/profile").mock(
        return_value=Response(200, json={"emailAddress": "user@gmail.com"})
    )
    config = exchange_gmail_code("auth-code", code_verifier="pkce-verifier")
    assert isinstance(config, GmailMailboxConfig)
    assert config.email_address == "user@gmail.com"
    assert config.access_token == "access-token"
    assert config.refresh_token == "refresh-token"
    assert config.token_expiry is not None
    assert b"code_verifier=pkce-verifier" in route.calls.last.request.content


def test_decode_rejects_wrong_token_type() -> None:
    payload = {
        "sub": "1",
        "type": "access",
        "exp": 9999999999,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    try:
        decode_gmail_oauth_state(token)
        raised = False
    except Exception:
        raised = True
    assert raised


@respx.mock
def test_revoke_gmail_tokens_posts_refresh_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    route = respx.post("https://oauth2.googleapis.com/revoke").mock(return_value=Response(200))
    revoke_gmail_tokens(
        GmailMailboxConfig(
            email_address="user@gmail.com",
            access_token="access",
            refresh_token="refresh-to-revoke",
        )
    )
    assert route.called
    assert route.calls.last.request.content == b"token=refresh-to-revoke"


@respx.mock
def test_revoke_gmail_tokens_raises_on_http_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    respx.post("https://oauth2.googleapis.com/revoke").mock(return_value=Response(400))
    with pytest.raises(GmailOAuthError, match="token revoke failed"):
        revoke_gmail_tokens(
            GmailMailboxConfig(
                email_address="user@gmail.com",
                access_token="access",
                refresh_token="refresh-to-revoke",
            )
        )
