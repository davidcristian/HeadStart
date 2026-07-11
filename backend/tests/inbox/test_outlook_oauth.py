"""Tests for Outlook OAuth helpers (mocked HTTP)."""

import jwt
import respx
from httpx import Response

from app.core.config import settings
from app.inbox.outlook_oauth import (
    build_outlook_authorization_url,
    create_outlook_oauth_state,
    decode_outlook_oauth_state,
    exchange_outlook_code,
    outlook_oauth_configured,
)
from app.inbox.types import OutlookMailboxConfig


def test_outlook_oauth_configured_requires_all_vars(monkeypatch) -> None:
    monkeypatch.setattr(settings, "outlook_oauth_client_id", "")
    monkeypatch.setattr(settings, "outlook_oauth_client_secret", "")
    monkeypatch.setattr(settings, "outlook_oauth_redirect_uri", "")
    assert outlook_oauth_configured() is False

    monkeypatch.setattr(settings, "outlook_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "outlook_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "outlook_oauth_redirect_uri", "http://localhost/callback")
    assert outlook_oauth_configured() is True


def test_outlook_oauth_state_round_trip() -> None:
    issued = create_outlook_oauth_state(42)
    assert decode_outlook_oauth_state(issued.state) == (42, issued.nonce, issued.code_verifier)


def test_build_authorization_url_contains_client_id_and_pkce(monkeypatch) -> None:
    from app.inbox.mailbox_oauth_state import code_challenge_s256

    monkeypatch.setattr(settings, "outlook_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "outlook_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "outlook_oauth_redirect_uri", "http://localhost/callback")
    url = build_outlook_authorization_url(state="signed-state", code_verifier="verifier-value")
    assert "client_id=client-id" in url
    assert "state=signed-state" in url
    assert "code_challenge_method=S256" in url
    assert f"code_challenge={code_challenge_s256('verifier-value')}" in url


@respx.mock
def test_exchange_outlook_code_returns_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "outlook_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "outlook_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "outlook_oauth_redirect_uri", "http://localhost/callback")
    route = respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
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
    respx.get("https://graph.microsoft.com/v1.0/me").mock(
        return_value=Response(200, json={"mail": "user@outlook.test"})
    )
    config = exchange_outlook_code("auth-code", code_verifier="pkce-verifier")
    assert isinstance(config, OutlookMailboxConfig)
    assert config.email_address == "user@outlook.test"
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
        decode_outlook_oauth_state(token)
        raised = False
    except Exception:
        raised = True
    assert raised
