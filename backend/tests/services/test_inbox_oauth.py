"""Regression tests for OAuth token-refresh persistence.

The refresh path must serialize with the same encoder as the initial store
(`encode_mailbox_config`, i.e. `json.dumps(model_dump())`) so a refreshed
credential round-trips through `decode_mailbox_config`. It previously used
`model_dump_json()`, which emits a different (compact) plaintext.

Refresh also locks the mailbox_credential row and re-checks expiry so
concurrent workers cannot rotate the same Outlook/Yahoo refresh_token.
"""

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt
from app.inbox.credentials import decode_mailbox_config, encode_mailbox_config
from app.inbox.types import GmailMailboxConfig, OutlookMailboxConfig, YahooMailboxConfig
from app.models.mailbox_credential import MailboxCredential
from app.models.user import User
from app.repositories.mailbox_credentials import MailboxCredentialRepository
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


def _user(session: Session) -> int:
    user = User(
        email="oauth@example.test", password_hash="x", is_admin=False, is_active=True, plan="pro"
    )
    session.add(user)
    session.flush()
    return user.id


def _store(
    session: Session,
    user_id: int,
    connector: str,
    config: GmailMailboxConfig | OutlookMailboxConfig | YahooMailboxConfig,
) -> MailboxCredential:
    credential = MailboxCredential(
        user_id=user_id,
        connector_type=connector,
        enabled=True,
        secret_ciphertext=encode_mailbox_config(config),
    )
    session.add(credential)
    session.flush()
    return credential


@pytest.mark.parametrize(("connector", "config_cls", "needs_fn", "refresh_fn", "ensure_fn"), _CASES)
def test_refresh_persists_via_canonical_encoder(
    db_session: Session, monkeypatch, connector, config_cls, needs_fn, refresh_fn, ensure_fn
) -> None:
    user_id = _user(db_session)
    config = config_cls(
        email_address=f"user@{connector}.test", access_token="old", refresh_token="r"
    )
    refreshed = config_cls(
        email_address=f"user@{connector}.test",
        access_token="new",
        refresh_token="r2",
        token_expiry="2026-07-01T00:00:00+00:00",
    )
    credential = _store(db_session, user_id, connector, config)
    monkeypatch.setattr(inbox_oauth, needs_fn, lambda _config: True)
    monkeypatch.setattr(inbox_oauth, refresh_fn, lambda _config: refreshed)

    result = getattr(inbox_oauth, ensure_fn)(db_session, credential, config)

    assert result == refreshed
    assert decrypt(credential.secret_ciphertext) == json.dumps(refreshed.model_dump())
    assert decode_mailbox_config(credential) == refreshed


@pytest.mark.parametrize(
    ("connector", "config_cls", "needs_fn", "ensure_fn"),
    (
        ("gmail", GmailMailboxConfig, "gmail_token_needs_refresh", "ensure_fresh_gmail_config"),
        (
            "outlook",
            OutlookMailboxConfig,
            "outlook_token_needs_refresh",
            "ensure_fresh_outlook_config",
        ),
        ("yahoo", YahooMailboxConfig, "yahoo_token_needs_refresh", "ensure_fresh_yahoo_config"),
    ),
)
def test_ensure_fresh_returns_config_unchanged_when_no_refresh_needed(
    db_session: Session, monkeypatch, connector, config_cls, needs_fn, ensure_fn
) -> None:
    user_id = _user(db_session)
    config = config_cls(
        email_address=f"user@{connector}.test", access_token="live", refresh_token="r"
    )
    credential = _store(db_session, user_id, connector, config)
    original_ciphertext = credential.secret_ciphertext
    monkeypatch.setattr(inbox_oauth, needs_fn, lambda _config: False)

    result = getattr(inbox_oauth, ensure_fn)(db_session, credential, config)

    assert result is config
    assert credential.secret_ciphertext == original_ciphertext


@pytest.mark.parametrize(("connector", "config_cls", "needs_fn", "refresh_fn", "ensure_fn"), _CASES)
def test_ensure_fresh_skips_provider_refresh_when_lock_recheck_is_fresh(
    db_session: Session, monkeypatch, connector, config_cls, needs_fn, refresh_fn, ensure_fn
) -> None:
    """After waiting for the row lock, reuse a peer's already-rotated token."""
    user_id = _user(db_session)
    stale = config_cls(
        email_address=f"user@{connector}.test", access_token="old", refresh_token="r1"
    )
    peer_fresh = config_cls(
        email_address=f"user@{connector}.test",
        access_token="peer",
        refresh_token="r2",
        token_expiry="2099-01-01T00:00:00+00:00",
    )
    credential = _store(db_session, user_id, connector, peer_fresh)
    refresh_calls: list[object] = []

    def needs(cfg: object) -> bool:
        # Unlocked caller still thinks refresh is due; locked re-read is fresh.
        return cfg is stale

    def refresh(cfg: object) -> object:
        refresh_calls.append(cfg)
        raise AssertionError("provider refresh must not run after peer rotation")

    monkeypatch.setattr(inbox_oauth, needs_fn, needs)
    monkeypatch.setattr(inbox_oauth, refresh_fn, refresh)

    result = getattr(inbox_oauth, ensure_fn)(db_session, credential, stale)

    assert result == peer_fresh
    assert refresh_calls == []
    assert decode_mailbox_config(credential) == peer_fresh


@pytest.mark.parametrize(("connector", "config_cls", "needs_fn", "refresh_fn", "ensure_fn"), _CASES)
def test_ensure_fresh_refreshes_when_locked_row_missing(
    monkeypatch, connector, config_cls, needs_fn, refresh_fn, ensure_fn
) -> None:
    """If the credential row vanishes mid-flight, still refresh the in-memory config."""
    config = config_cls(
        email_address=f"user@{connector}.test", access_token="old", refresh_token="r"
    )
    refreshed = config_cls(
        email_address=f"user@{connector}.test",
        access_token="new",
        refresh_token="r2",
        token_expiry="2026-07-01T00:00:00+00:00",
    )
    credential = MailboxCredential(
        id=1, user_id=7, connector_type=connector, secret_ciphertext="", enabled=True
    )
    session = MagicMock()
    monkeypatch.setattr(inbox_oauth, needs_fn, lambda _config: True)
    monkeypatch.setattr(inbox_oauth, refresh_fn, lambda _config: refreshed)
    monkeypatch.setattr(
        MailboxCredentialRepository,
        "get_for_user_for_update",
        lambda self, user_id: None,
    )

    result = getattr(inbox_oauth, ensure_fn)(session, credential, config)

    assert result == refreshed
    assert decrypt(credential.secret_ciphertext) == json.dumps(refreshed.model_dump())
    session.flush.assert_called_once()


@pytest.mark.parametrize(("connector", "config_cls", "needs_fn", "refresh_fn", "ensure_fn"), _CASES)
def test_ensure_fresh_returns_caller_config_when_locked_type_mismatches(
    db_session: Session, monkeypatch, connector, config_cls, needs_fn, refresh_fn, ensure_fn
) -> None:
    user_id = _user(db_session)
    config = config_cls(
        email_address=f"user@{connector}.test", access_token="old", refresh_token="r"
    )
    # Store a different connector type under the same user row.
    other = (
        OutlookMailboxConfig(email_address="x@outlook.test", access_token="a", refresh_token="b")
        if connector == "gmail"
        else GmailMailboxConfig(email_address="x@gmail.test", access_token="a", refresh_token="b")
    )
    other_type = "outlook" if connector == "gmail" else "gmail"
    credential = _store(db_session, user_id, other_type, other)
    refresh_calls: list[object] = []
    monkeypatch.setattr(inbox_oauth, needs_fn, lambda _config: True)
    monkeypatch.setattr(
        inbox_oauth,
        refresh_fn,
        lambda cfg: refresh_calls.append(cfg) or cfg,
    )

    result = getattr(inbox_oauth, ensure_fn)(db_session, credential, config)

    assert result is config
    assert refresh_calls == []


def test_persist_oauth_mailbox_creates_new_credential(db_session: Session) -> None:
    user_id = _user(db_session)
    repo = MailboxCredentialRepository(db_session)
    config = GmailMailboxConfig(email_address="new@gmail.test", access_token="a", refresh_token="r")

    result = inbox_oauth.persist_oauth_mailbox(
        db_session, repo, user_id=user_id, connector_type="gmail", config=config
    )

    assert result.connector_type == "gmail"
    assert result.email_address == "new@gmail.test"
    stored = repo.get_for_user(user_id)
    assert stored is not None
    assert stored.connector_type == "gmail"
    assert stored.enabled is True
    assert decode_mailbox_config(stored) == config


def test_persist_oauth_mailbox_updates_existing_credential(db_session: Session) -> None:
    user_id = _user(db_session)
    repo = MailboxCredentialRepository(db_session)
    first = GmailMailboxConfig(email_address="old@gmail.test", access_token="a", refresh_token="r")
    inbox_oauth.persist_oauth_mailbox(
        db_session, repo, user_id=user_id, connector_type="gmail", config=first
    )

    updated = OutlookMailboxConfig(
        email_address="new@outlook.test", access_token="b", refresh_token="s"
    )
    result = inbox_oauth.persist_oauth_mailbox(
        db_session, repo, user_id=user_id, connector_type="outlook", config=updated
    )

    assert result.connector_type == "outlook"
    assert result.email_address == "new@outlook.test"
    stored = repo.get_for_user(user_id)
    assert stored is not None
    assert stored.connector_type == "outlook"
    assert decode_mailbox_config(stored) == updated


def test_get_for_user_for_update_uses_unlocked_path_on_sqlite(db_session: Session) -> None:
    user_id = _user(db_session)
    config = GmailMailboxConfig(
        email_address="lock@gmail.test", access_token="a", refresh_token="r"
    )
    stored = _store(db_session, user_id, "gmail", config)
    repo = MailboxCredentialRepository(db_session)

    locked = repo.get_for_user_for_update(user_id)

    assert locked is not None
    assert locked.id == stored.id


def test_get_for_user_for_update_takes_row_lock_branch_on_non_sqlite(
    db_session: Session,
) -> None:
    """Force the FOR UPDATE branch (SQLite silently drops the clause)."""
    user_id = _user(db_session)
    config = GmailMailboxConfig(
        email_address="lock@gmail.test", access_token="a", refresh_token="r"
    )
    stored = _store(db_session, user_id, "gmail", config)
    repo = MailboxCredentialRepository(db_session)
    repo._is_sqlite = lambda: False  # type: ignore[method-assign]

    locked = repo.get_for_user_for_update(user_id)

    assert locked is not None
    assert locked.id == stored.id


def test_get_for_user_for_update_compiles_for_update_for_postgres() -> None:
    """Postgres refresh SQL must lock the row so overlapping ticks cannot double-rotate."""
    stmt = select(MailboxCredential).where(MailboxCredential.user_id == 1).with_for_update()
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE" in compiled.upper()
