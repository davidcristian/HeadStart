"""Tests for Yahoo OAuth helpers (mocked HTTP)."""

import jwt
import respx
from httpx import Response

from app.core.config import settings
from app.inbox.types import YahooMailboxConfig
from app.inbox.yahoo_oauth import (
    build_yahoo_authorization_url,
    create_yahoo_oauth_state,
    decode_yahoo_oauth_state,
    exchange_yahoo_code,
    yahoo_oauth_configured,
)
from app.inbox.yahoo_sasl import build_yahoo_oauth_bearer_string


def test_yahoo_oauth_configured_requires_all_vars(monkeypatch) -> None:
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "")
    assert yahoo_oauth_configured() is False

    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "http://localhost/callback")
    assert yahoo_oauth_configured() is True


def test_yahoo_oauth_state_round_trip() -> None:
    state = create_yahoo_oauth_state(42)
    assert decode_yahoo_oauth_state(state) == 42


def test_build_authorization_url_contains_client_id(monkeypatch) -> None:
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "http://localhost/callback")
    url = build_yahoo_authorization_url(state="signed-state")
    assert "client_id=client-id" in url
    assert "state=signed-state" in url
    assert "mail-w" in url


@respx.mock
def test_exchange_yahoo_code_returns_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "http://localhost/callback")
    respx.post("https://api.login.yahoo.com/oauth2/get_token").mock(
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
    respx.get("https://api.login.yahoo.com/openid/v1/userinfo").mock(
        return_value=Response(200, json={"email": "user@yahoo.test"})
    )
    config = exchange_yahoo_code("auth-code")
    assert isinstance(config, YahooMailboxConfig)
    assert config.email_address == "user@yahoo.test"
    assert config.access_token == "access-token"
    assert config.refresh_token == "refresh-token"
    assert config.token_expiry is not None


def test_decode_rejects_wrong_token_type() -> None:
    payload = {
        "sub": "1",
        "type": "access",
        "exp": 9999999999,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    try:
        decode_yahoo_oauth_state(token)
        raised = False
    except Exception:
        raised = True
    assert raised


def test_oauth_bearer_string_includes_host_and_token() -> None:
    auth_string = build_yahoo_oauth_bearer_string(
        "user@yahoo.test",
        "token-value",
        host="imap.mail.yahoo.com",
        port=993,
    )
    assert "a=user@yahoo.test" in auth_string
    assert "host=imap.mail.yahoo.com" in auth_string
    assert "port=993" in auth_string
    assert "auth=Bearer token-value" in auth_string
