"""Branch coverage for Gmail/Outlook/Yahoo OAuth refresh + expiry logic.

Split sibling of test_oauth_branches.py: this file drives the refresh_* branches
and the *_token_needs_refresh expiry logic; the require/decode/exchange branches
live in test_oauth_branches.py.
"""

from datetime import timedelta

import pytest
import respx
from httpx import Response

from app.core.config import settings
from app.inbox import gmail_oauth, outlook_oauth, yahoo_oauth
from app.inbox.types import (
    GmailMailboxConfig,
    OutlookMailboxConfig,
    YahooMailboxConfig,
)
from app.models.base import utcnow

GMAIL_TOKEN = "https://oauth2.googleapis.com/token"
OUTLOOK_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
YAHOO_TOKEN = "https://api.login.yahoo.com/oauth2/get_token"


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
# refresh_* branches
# --------------------------------------------------------------------------- #


@respx.mock
def test_gmail_refresh_paths(monkeypatch) -> None:
    _configure_gmail(monkeypatch)
    cfg = GmailMailboxConfig(email_address="u@gmail.com", access_token="old", refresh_token="r")

    respx.post(GMAIL_TOKEN).mock(return_value=Response(401))
    with pytest.raises(gmail_oauth.GmailOAuthError, match="refresh"):
        gmail_oauth.refresh_gmail_access_token(cfg)

    respx.post(GMAIL_TOKEN).mock(return_value=Response(200, json={}))
    with pytest.raises(gmail_oauth.GmailOAuthError, match="access token"):
        gmail_oauth.refresh_gmail_access_token(cfg)

    respx.post(GMAIL_TOKEN).mock(return_value=Response(200, json={"access_token": "new"}))
    kept = gmail_oauth.refresh_gmail_access_token(cfg.model_copy(update={"token_expiry": "keep"}))
    assert kept.access_token == "new"
    assert kept.token_expiry == "keep"

    respx.post(GMAIL_TOKEN).mock(
        return_value=Response(200, json={"access_token": "new2", "expires_in": 3600})
    )
    refreshed = gmail_oauth.refresh_gmail_access_token(cfg)
    assert refreshed.token_expiry is not None


@respx.mock
def test_outlook_refresh_paths(monkeypatch) -> None:
    _configure_outlook(monkeypatch)
    cfg = OutlookMailboxConfig(
        email_address="u@outlook.test", access_token="old", refresh_token="keep"
    )

    respx.post(OUTLOOK_TOKEN).mock(return_value=Response(401))
    with pytest.raises(outlook_oauth.OutlookOAuthError, match="refresh"):
        outlook_oauth.refresh_outlook_access_token(cfg)

    respx.post(OUTLOOK_TOKEN).mock(return_value=Response(200, json={}))
    with pytest.raises(outlook_oauth.OutlookOAuthError, match="access token"):
        outlook_oauth.refresh_outlook_access_token(cfg)

    respx.post(OUTLOOK_TOKEN).mock(return_value=Response(200, json={"access_token": "new"}))
    kept = outlook_oauth.refresh_outlook_access_token(cfg)
    assert kept.refresh_token == "keep"

    respx.post(OUTLOOK_TOKEN).mock(
        return_value=Response(
            200, json={"access_token": "new2", "refresh_token": "rot", "expires_in": 3600}
        )
    )
    rotated = outlook_oauth.refresh_outlook_access_token(cfg)
    assert rotated.refresh_token == "rot"
    assert rotated.token_expiry is not None


@respx.mock
def test_yahoo_refresh_paths(monkeypatch) -> None:
    _configure_yahoo(monkeypatch)
    cfg = YahooMailboxConfig(email_address="u@yahoo.test", access_token="old", refresh_token="keep")

    respx.post(YAHOO_TOKEN).mock(return_value=Response(401))
    with pytest.raises(yahoo_oauth.YahooOAuthError, match="refresh"):
        yahoo_oauth.refresh_yahoo_access_token(cfg)

    respx.post(YAHOO_TOKEN).mock(return_value=Response(200, json={}))
    with pytest.raises(yahoo_oauth.YahooOAuthError, match="access token"):
        yahoo_oauth.refresh_yahoo_access_token(cfg)

    respx.post(YAHOO_TOKEN).mock(return_value=Response(200, json={"access_token": "new"}))
    kept = yahoo_oauth.refresh_yahoo_access_token(cfg)
    assert kept.refresh_token == "keep"

    respx.post(YAHOO_TOKEN).mock(
        return_value=Response(
            200, json={"access_token": "new2", "refresh_token": "rot", "expires_in": 3600}
        )
    )
    rotated = yahoo_oauth.refresh_yahoo_access_token(cfg)
    assert rotated.refresh_token == "rot"
    assert rotated.token_expiry is not None


# --------------------------------------------------------------------------- #
# *_token_needs_refresh branches
# --------------------------------------------------------------------------- #


def _needs_refresh_cases(config_cls, needs_refresh) -> None:
    no_token = config_cls(email_address="u@a.test", access_token="a", refresh_token="r").model_copy(
        update={"access_token": ""}
    )
    assert needs_refresh(no_token) is True

    no_expiry = config_cls(email_address="u@a.test", access_token="a", refresh_token="r")
    assert needs_refresh(no_expiry) is False

    bad = config_cls(
        email_address="u@a.test", access_token="a", refresh_token="r", token_expiry="bad"
    )
    assert needs_refresh(bad) is True

    naive = config_cls(
        email_address="u@a.test",
        access_token="a",
        refresh_token="r",
        token_expiry=utcnow().replace(tzinfo=None).isoformat(),
    )
    assert needs_refresh(naive) is True

    far = config_cls(
        email_address="u@a.test",
        access_token="a",
        refresh_token="r",
        token_expiry=(utcnow() + timedelta(hours=2)).isoformat(),
    )
    assert needs_refresh(far) is False


def test_gmail_token_needs_refresh() -> None:
    _needs_refresh_cases(GmailMailboxConfig, gmail_oauth.gmail_token_needs_refresh)


def test_outlook_token_needs_refresh() -> None:
    _needs_refresh_cases(OutlookMailboxConfig, outlook_oauth.outlook_token_needs_refresh)


def test_yahoo_token_needs_refresh() -> None:
    _needs_refresh_cases(YahooMailboxConfig, yahoo_oauth.yahoo_token_needs_refresh)
