"""Unit tests for mailbox OAuth teardown on account deletion."""

from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.credentials import encode_mailbox_config
from app.inbox.types import (
    GmailMailboxConfig,
    MailboxConfig,
    OutlookMailboxConfig,
    YahooMailboxConfig,
)
from app.models.mailbox_credential import MailboxCredential
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.repositories.users import UserRepository
from app.schemas.auth import DeleteAccountRequest, RegisterRequest
from app.services.auth import AuthService
from app.services.mailbox_account_cleanup import release_mailbox_oauth


def _gmail_config() -> GmailMailboxConfig:
    return GmailMailboxConfig(
        email_address="user@gmail.com",
        access_token="access-token",
        refresh_token="refresh-token",
    )


def _yahoo_config() -> YahooMailboxConfig:
    return YahooMailboxConfig(
        email_address="user@yahoo.com",
        access_token="access-token",
        refresh_token="refresh-token",
    )


def _outlook_config() -> OutlookMailboxConfig:
    return OutlookMailboxConfig(
        email_address="user@outlook.com",
        access_token="access-token",
        refresh_token="refresh-token",
    )


def _seed_mailbox(
    db_session: Session,
    user_id: int,
    *,
    connector_type: str,
    config: GmailMailboxConfig | YahooMailboxConfig | OutlookMailboxConfig | MailboxConfig,
) -> MailboxCredential:
    credential = MailboxCredential(
        user_id=user_id,
        connector_type=connector_type,
        secret_ciphertext=encode_mailbox_config(config),
        enabled=True,
    )
    return MailboxCredentialRepository(db_session).add(credential)


def _register(db_session: Session, email: str) -> int:
    user = AuthService(db_session).register(RegisterRequest(email=email, password="password123"))
    assert user is not None
    return user.id


@respx.mock
def test_release_revokes_gmail_grant(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    user_id = _register(db_session, "gmail-revoke@example.com")
    _seed_mailbox(db_session, user_id, connector_type="gmail", config=_gmail_config())
    route = respx.post("https://oauth2.googleapis.com/revoke").mock(return_value=Response(200))
    release_mailbox_oauth(db_session, user_id)
    assert route.called
    assert route.calls.last.request.content == b"token=refresh-token"


@respx.mock
def test_release_revokes_yahoo_grant(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "http://localhost/callback")
    user_id = _register(db_session, "yahoo-revoke@example.com")
    _seed_mailbox(db_session, user_id, connector_type="yahoo", config=_yahoo_config())
    route = respx.post("https://api.login.yahoo.com/oauth2/revoke").mock(return_value=Response(200))
    release_mailbox_oauth(db_session, user_id)
    assert route.called
    assert b"token=refresh-token" in route.calls.last.request.content


def test_release_skips_when_no_mailbox(db_session: Session) -> None:
    user_id = _register(db_session, "no-mailbox@example.com")
    release_mailbox_oauth(db_session, user_id)  # must not raise


def test_release_outlook_discards_locally_only(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _register(db_session, "outlook-revoke@example.com")
    _seed_mailbox(db_session, user_id, connector_type="outlook", config=_outlook_config())
    with caplog.at_level("INFO", logger="app.services.mailbox_account_cleanup"):
        release_mailbox_oauth(db_session, user_id)
    assert any("no per-app Microsoft revoke API" in r.getMessage() for r in caplog.records)


def test_release_skips_imap_smtp(db_session: Session) -> None:
    user_id = _register(db_session, "imap-revoke@example.com")
    _seed_mailbox(
        db_session,
        user_id,
        connector_type="imap_smtp",
        config=MailboxConfig(
            imap_host="imap.example.com",
            imap_user="u@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com",
        ),
    )
    release_mailbox_oauth(db_session, user_id)  # must not raise


@respx.mock
def test_release_swallows_gmail_revoke_errors(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "gmail_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "gmail_oauth_redirect_uri", "http://localhost/callback")
    user_id = _register(db_session, "gmail-fail@example.com")
    _seed_mailbox(db_session, user_id, connector_type="gmail", config=_gmail_config())
    respx.post("https://oauth2.googleapis.com/revoke").mock(return_value=Response(400))
    release_mailbox_oauth(db_session, user_id)  # must not raise


@respx.mock
def test_release_swallows_yahoo_revoke_errors(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "yahoo_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "yahoo_oauth_redirect_uri", "http://localhost/callback")
    user_id = _register(db_session, "yahoo-fail@example.com")
    _seed_mailbox(db_session, user_id, connector_type="yahoo", config=_yahoo_config())
    respx.post("https://api.login.yahoo.com/oauth2/revoke").mock(return_value=Response(500))
    release_mailbox_oauth(db_session, user_id)  # must not raise


def test_release_swallows_decode_errors(db_session: Session) -> None:
    user_id = _register(db_session, "bad-mailbox@example.com")
    credential = MailboxCredential(
        user_id=user_id,
        connector_type="gmail",
        secret_ciphertext="not-valid-fernet",
        enabled=True,
    )
    MailboxCredentialRepository(db_session).add(credential)
    release_mailbox_oauth(db_session, user_id)  # must not raise


@patch("app.services.auth_account.release_mailbox_oauth")
@patch("app.services.auth_account.release_stripe_billing")
def test_delete_account_releases_mailbox_oauth_before_local_delete(
    mock_stripe: MagicMock,
    mock_mailbox: MagicMock,
    db_session: Session,
) -> None:
    service = AuthService(db_session)
    user = service.register(
        RegisterRequest(email="mailbox-delete@example.com", password="password123")
    )
    assert user is not None
    service.delete_account(user.id, DeleteAccountRequest(password="password123"))
    mock_stripe.assert_called_once()
    mock_mailbox.assert_called_once()
    assert mock_mailbox.call_args.args[1] == user.id
    assert UserRepository(db_session).get(user.id) is None
