"""Tests for the inbox mailbox OAuth authorize/callback wrappers."""

from unittest.mock import MagicMock

import pytest

from app.inbox.types import GmailMailboxConfig, OutlookMailboxConfig, YahooMailboxConfig
from app.services import inbox_mailbox_oauth

_AUTHORIZE_CASES = (
    (
        "gmail",
        GmailMailboxConfig,
        "require_gmail_oauth_configured",
        "create_gmail_oauth_state",
        "build_gmail_authorization_url",
        "gmail_authorize_url",
    ),
    (
        "outlook",
        OutlookMailboxConfig,
        "require_outlook_oauth_configured",
        "create_outlook_oauth_state",
        "build_outlook_authorization_url",
        "outlook_authorize_url",
    ),
    (
        "yahoo",
        YahooMailboxConfig,
        "require_yahoo_oauth_configured",
        "create_yahoo_oauth_state",
        "build_yahoo_authorization_url",
        "yahoo_authorize_url",
    ),
)


@pytest.mark.parametrize(
    ("connector", "config_cls", "require_fn", "state_fn", "build_fn", "authorize_fn"),
    _AUTHORIZE_CASES,
)
def test_authorize_url_builds_consent_link(
    monkeypatch, connector, config_cls, require_fn, state_fn, build_fn, authorize_fn
) -> None:
    require = MagicMock()
    monkeypatch.setattr(inbox_mailbox_oauth, require_fn, require)
    monkeypatch.setattr(
        inbox_mailbox_oauth,
        state_fn,
        lambda user_id: type(
            "Issued",
            (),
            {"state": f"state-{user_id}", "nonce": f"nonce-{user_id}"},
        )(),
    )
    monkeypatch.setattr(
        inbox_mailbox_oauth,
        build_fn,
        lambda *, state: f"https://{connector}.example/auth?state={state}",
    )

    response, nonce = getattr(inbox_mailbox_oauth, authorize_fn)(11)

    require.assert_called_once_with()
    assert nonce == "nonce-11"
    assert response.authorization_url == f"https://{connector}.example/auth?state=state-11"


_CALLBACK_CASES = (
    (
        "gmail",
        GmailMailboxConfig,
        "decode_gmail_oauth_state",
        "exchange_gmail_code",
        "complete_gmail_oauth",
    ),
    (
        "outlook",
        OutlookMailboxConfig,
        "decode_outlook_oauth_state",
        "exchange_outlook_code",
        "complete_outlook_oauth",
    ),
    (
        "yahoo",
        YahooMailboxConfig,
        "decode_yahoo_oauth_state",
        "exchange_yahoo_code",
        "complete_yahoo_oauth",
    ),
)


@pytest.mark.parametrize(
    ("connector", "config_cls", "decode_fn", "exchange_fn", "complete_fn"),
    _CALLBACK_CASES,
)
def test_complete_oauth_persists_via_helper(
    monkeypatch, connector, config_cls, decode_fn, exchange_fn, complete_fn
) -> None:
    config = config_cls(email_address=f"user@{connector}.test", access_token="a", refresh_token="r")
    monkeypatch.setattr(inbox_mailbox_oauth, decode_fn, lambda state: (42, "nonce-42"))
    monkeypatch.setattr(inbox_mailbox_oauth, exchange_fn, lambda code: config)
    persist = MagicMock(return_value="callback-result")
    monkeypatch.setattr(inbox_mailbox_oauth, "persist_oauth_mailbox", persist)

    session = MagicMock()
    repo = MagicMock()
    result = getattr(inbox_mailbox_oauth, complete_fn)(
        session,
        repo,
        code="the-code",
        state="the-state",
        oauth_nonce="nonce-42",
    )

    assert result == "callback-result"
    persist.assert_called_once_with(
        session,
        repo,
        user_id=42,
        connector_type=connector,
        config=config,
    )


_AVAILABLE_CASES = (
    ("gmail_oauth_configured", "gmail_oauth_available"),
    ("outlook_oauth_configured", "outlook_oauth_available"),
    ("yahoo_oauth_configured", "yahoo_oauth_available"),
)


@pytest.mark.parametrize(("configured_fn", "available_fn"), _AVAILABLE_CASES)
@pytest.mark.parametrize("configured", [True, False])
def test_oauth_available_reflects_configured(
    monkeypatch, configured_fn, available_fn, configured
) -> None:
    monkeypatch.setattr(inbox_mailbox_oauth, configured_fn, lambda: configured)
    assert getattr(inbox_mailbox_oauth, available_fn)() is configured
