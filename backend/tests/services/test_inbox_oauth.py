"""Regression tests for OAuth token-refresh persistence.

The refresh path must serialize with the same encoder as the initial store
(`encode_mailbox_config`, i.e. `json.dumps(model_dump())`) so a refreshed
credential round-trips through `decode_mailbox_config`. It previously used
`model_dump_json()`, which emits a different (compact) plaintext.
"""

import json
from unittest.mock import MagicMock

import pytest

from app.core.crypto import decrypt
from app.inbox.credentials import decode_mailbox_config
from app.inbox.types import GmailMailboxConfig, OutlookMailboxConfig, YahooMailboxConfig
from app.models.mailbox_credential import MailboxCredential
from app.services import inbox_oauth

_CASES = (
    (
        "gmail",
        GmailMailboxConfig,
        "gmail_token_needs_refresh",
        "refresh_gmail_access_token",
        "ensure_fresh_gmail_config",
    ),
    (
        "outlook",
        OutlookMailboxConfig,
        "outlook_token_needs_refresh",
        "refresh_outlook_access_token",
        "ensure_fresh_outlook_config",
    ),
    (
        "yahoo",
        YahooMailboxConfig,
        "yahoo_token_needs_refresh",
        "refresh_yahoo_access_token",
        "ensure_fresh_yahoo_config",
    ),
)


@pytest.mark.parametrize(("connector", "config_cls", "needs_fn", "refresh_fn", "ensure_fn"), _CASES)
def test_refresh_persists_via_canonical_encoder(
    monkeypatch, connector, config_cls, needs_fn, refresh_fn, ensure_fn
) -> None:
    config = config_cls(
        email_address=f"user@{connector}.test", access_token="old", refresh_token="r"
    )
    refreshed = config_cls(
        email_address=f"user@{connector}.test",
        access_token="new",
        refresh_token="r",
        token_expiry="2026-07-01T00:00:00+00:00",
    )
    monkeypatch.setattr(inbox_oauth, needs_fn, lambda _config: True)
    monkeypatch.setattr(inbox_oauth, refresh_fn, lambda _config: refreshed)
    credential = MailboxCredential(
        id=1, user_id=7, connector_type=connector, secret_ciphertext="", enabled=True
    )

    result = getattr(inbox_oauth, ensure_fn)(MagicMock(), credential, config)

    assert result == refreshed
    # Persisted plaintext matches the canonical encoder, not model_dump_json().
    assert decrypt(credential.secret_ciphertext) == json.dumps(refreshed.model_dump())
    assert decode_mailbox_config(credential) == refreshed
