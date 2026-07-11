"""Branch coverage for Gmail/Outlook/Yahoo OAuth helpers (error paths).

Kept in a dedicated file so the happy-path tests in test_{gmail,outlook,yahoo}_oauth.py
stay focused; this file drives the require/decode error branches and the exchange_*
error branches. The refresh/expiry logic lives in test_oauth_branches_refresh.py.
"""

import jwt
import pytest
import respx
from httpx import Response

from app.core.config import settings
from app.inbox import gmail_oauth, outlook_oauth, yahoo_oauth

GMAIL_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
OUTLOOK_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
OUTLOOK_ME = "https://graph.microsoft.com/v1.0/me"
YAHOO_TOKEN = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_USERINFO = "https://api.login.yahoo.com/openid/v1/userinfo"


def _configure_gmail(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/cb")


def _configure_outlook(monkeypatch) -> None:
    monkeypatch.setattr(settings, "outlook_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "outlook_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "outlook_oauth_redirect_uri", "http://localhost/cb")


def _configure_yahoo(monkeypatch) -> None:
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "http://localhost/cb")


# --------------------------------------------------------------------------- #
# require_*_configured + decode error branches
# --------------------------------------------------------------------------- #


def test_gmail_require_configured_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "")
    with pytest.raises(gmail_oauth.GmailOAuthError):
        gmail_oauth.require_gmail_oauth_configured()


def test_outlook_require_configured_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "outlook_oauth_client_id", "")
    with pytest.raises(outlook_oauth.OutlookOAuthError):
        outlook_oauth.require_outlook_oauth_configured()


def test_yahoo_require_configured_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "")
    with pytest.raises(yahoo_oauth.YahooOAuthError):
        yahoo_oauth.require_yahoo_oauth_configured()


def test_gmail_decode_rejects_garbage_and_bad_sub() -> None:
    with pytest.raises(gmail_oauth.GmailOAuthError):
        gmail_oauth.decode_gmail_oauth_state("not-a-jwt")
    token = jwt.encode(
        {"sub": "abc", "type": "gmail_oauth", "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(gmail_oauth.GmailOAuthError):
        gmail_oauth.decode_gmail_oauth_state(token)


def test_outlook_decode_rejects_garbage_and_bad_sub() -> None:
    with pytest.raises(outlook_oauth.OutlookOAuthError):
        outlook_oauth.decode_outlook_oauth_state("not-a-jwt")
    token = jwt.encode(
        {"sub": "abc", "type": "outlook_oauth", "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(outlook_oauth.OutlookOAuthError):
        outlook_oauth.decode_outlook_oauth_state(token)


def test_yahoo_decode_rejects_garbage_and_bad_sub() -> None:
    with pytest.raises(yahoo_oauth.YahooOAuthError):
        yahoo_oauth.decode_yahoo_oauth_state("not-a-jwt")
    token = jwt.encode(
        {"sub": "abc", "type": "yahoo_oauth", "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(yahoo_oauth.YahooOAuthError):
        yahoo_oauth.decode_yahoo_oauth_state(token)


# --------------------------------------------------------------------------- #
# exchange_* error branches
# --------------------------------------------------------------------------- #


@respx.mock
def test_gmail_exchange_errors(monkeypatch) -> None:
    _configure_gmail(monkeypatch)
    respx.post(GMAIL_TOKEN).mock(return_value=Response(400))
    with pytest.raises(gmail_oauth.GmailOAuthError, match="rejected"):
        gmail_oauth.exchange_gmail_code("code", code_verifier="pkce-verifier")

    respx.post(GMAIL_TOKEN).mock(return_value=Response(200, json={"refresh_token": "r"}))
    with pytest.raises(gmail_oauth.GmailOAuthError, match="access token"):
        gmail_oauth.exchange_gmail_code("code", code_verifier="pkce-verifier")

    respx.post(GMAIL_TOKEN).mock(return_value=Response(200, json={"access_token": "a"}))
    with pytest.raises(gmail_oauth.GmailOAuthError, match="refresh token"):
        gmail_oauth.exchange_gmail_code("code", code_verifier="pkce-verifier")


@respx.mock
def test_gmail_exchange_no_expiry_and_profile_paths(monkeypatch) -> None:
    _configure_gmail(monkeypatch)
    respx.post(GMAIL_TOKEN).mock(
        return_value=Response(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 0}
        )
    )
    respx.get(GMAIL_PROFILE).mock(return_value=Response(500))
    with pytest.raises(gmail_oauth.GmailOAuthError, match="profile"):
        gmail_oauth.exchange_gmail_code("code", code_verifier="pkce-verifier")

    respx.get(GMAIL_PROFILE).mock(return_value=Response(200, json={}))
    with pytest.raises(gmail_oauth.GmailOAuthError, match="email address"):
        gmail_oauth.exchange_gmail_code("code", code_verifier="pkce-verifier")

    respx.get(GMAIL_PROFILE).mock(return_value=Response(200, json={"emailAddress": "u@gmail.com"}))
    config = gmail_oauth.exchange_gmail_code("code", code_verifier="pkce-verifier")
    assert config.token_expiry is None


@respx.mock
def test_outlook_exchange_errors_and_upn_fallback(monkeypatch) -> None:
    _configure_outlook(monkeypatch)
    respx.post(OUTLOOK_TOKEN).mock(return_value=Response(400))
    with pytest.raises(outlook_oauth.OutlookOAuthError, match="rejected"):
        outlook_oauth.exchange_outlook_code("code", code_verifier="pkce-verifier")

    respx.post(OUTLOOK_TOKEN).mock(return_value=Response(200, json={"refresh_token": "r"}))
    with pytest.raises(outlook_oauth.OutlookOAuthError, match="access token"):
        outlook_oauth.exchange_outlook_code("code", code_verifier="pkce-verifier")

    respx.post(OUTLOOK_TOKEN).mock(return_value=Response(200, json={"access_token": "a"}))
    with pytest.raises(outlook_oauth.OutlookOAuthError, match="refresh token"):
        outlook_oauth.exchange_outlook_code("code", code_verifier="pkce-verifier")

    respx.post(OUTLOOK_TOKEN).mock(
        return_value=Response(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 0}
        )
    )
    respx.get(OUTLOOK_ME).mock(return_value=Response(500))
    with pytest.raises(outlook_oauth.OutlookOAuthError, match="profile"):
        outlook_oauth.exchange_outlook_code("code", code_verifier="pkce-verifier")

    respx.get(OUTLOOK_ME).mock(return_value=Response(200, json={}))
    with pytest.raises(outlook_oauth.OutlookOAuthError, match="email address"):
        outlook_oauth.exchange_outlook_code("code", code_verifier="pkce-verifier")

    respx.get(OUTLOOK_ME).mock(
        return_value=Response(200, json={"userPrincipalName": "u@outlook.test"})
    )
    config = outlook_oauth.exchange_outlook_code("code", code_verifier="pkce-verifier")
    assert config.email_address == "u@outlook.test"
    assert config.token_expiry is None


@respx.mock
def test_yahoo_exchange_errors_and_no_expiry(monkeypatch) -> None:
    _configure_yahoo(monkeypatch)
    respx.post(YAHOO_TOKEN).mock(return_value=Response(400))
    with pytest.raises(yahoo_oauth.YahooOAuthError, match="rejected"):
        yahoo_oauth.exchange_yahoo_code("code", code_verifier="pkce-verifier")

    respx.post(YAHOO_TOKEN).mock(return_value=Response(200, json={"refresh_token": "r"}))
    with pytest.raises(yahoo_oauth.YahooOAuthError, match="access token"):
        yahoo_oauth.exchange_yahoo_code("code", code_verifier="pkce-verifier")

    respx.post(YAHOO_TOKEN).mock(return_value=Response(200, json={"access_token": "a"}))
    with pytest.raises(yahoo_oauth.YahooOAuthError, match="refresh token"):
        yahoo_oauth.exchange_yahoo_code("code", code_verifier="pkce-verifier")

    respx.post(YAHOO_TOKEN).mock(
        return_value=Response(
            200, json={"access_token": "a", "refresh_token": "r", "expires_in": 0}
        )
    )
    respx.get(YAHOO_USERINFO).mock(return_value=Response(500))
    with pytest.raises(yahoo_oauth.YahooOAuthError, match="profile"):
        yahoo_oauth.exchange_yahoo_code("code", code_verifier="pkce-verifier")

    respx.get(YAHOO_USERINFO).mock(return_value=Response(200, json={}))
    with pytest.raises(yahoo_oauth.YahooOAuthError, match="email address"):
        yahoo_oauth.exchange_yahoo_code("code", code_verifier="pkce-verifier")

    respx.get(YAHOO_USERINFO).mock(return_value=Response(200, json={"email": "u@yahoo.test"}))
    config = yahoo_oauth.exchange_yahoo_code("code", code_verifier="pkce-verifier")
    assert config.token_expiry is None
