"""Coverage tests for InboxService connectors, OAuth wrappers, and resolution."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.inbox.types import (
    ConnectionTestResult,
    FastmailMailboxConfig,
    FetchResult,
    OutboundMessage,
    SendResult,
)
from app.models.user import User
from app.schemas.mailbox import (
    GmailAuthorizeResponse,
    GmailOAuthCallbackResult,
    MailboxCredentialUpsert,
    OutlookAuthorizeResponse,
    YahooAuthorizeResponse,
)
from app.services import inbox as inbox_module
from app.services.inbox import InboxService
from tests.services.test_inbox import _sample_config


def _user(session: Session, email: str = "inboxcov@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user.id


def test_upsert_rejects_unsupported_connector(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    with pytest.raises(ValidationError):
        svc.upsert(
            user_id,
            MailboxCredentialUpsert(
                connector_type="gmail",
                config=_sample_config(),
            ),
        )


def test_upsert_updates_existing_credential(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    updated = svc.upsert(
        user_id,
        MailboxCredentialUpsert(
            connector_type="fastmail",
            config=FastmailMailboxConfig(email_address="a@fastmail.test", api_token="t"),
        ),
    )
    assert updated.connector_type == "fastmail"


def test_get_read_missing_raises(db_session: Session) -> None:
    user_id = _user(db_session)
    with pytest.raises(NotFoundError):
        InboxService(db_session).get_read(user_id)


def test_get_read_returns_credential(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    read = svc.get_read(user_id)
    assert read.imap_host == "imap.example.com"


def test_get_read_optional_returns_none(db_session: Session) -> None:
    user_id = _user(db_session)
    assert InboxService(db_session).get_read_optional(user_id) is None


def test_delete_missing_raises(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    with pytest.raises(NotFoundError):
        InboxService(db_session).delete(user_id)


def test_oauth_authorize_and_callback_wrappers(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)

    monkeypatch.setattr(
        inbox_module.inbox_mailbox_oauth,
        "gmail_authorize_url",
        lambda uid: GmailAuthorizeResponse(authorization_url="https://g/auth"),
    )
    monkeypatch.setattr(
        inbox_module.inbox_mailbox_oauth,
        "outlook_authorize_url",
        lambda uid: OutlookAuthorizeResponse(authorization_url="https://o/auth"),
    )
    monkeypatch.setattr(
        inbox_module.inbox_mailbox_oauth,
        "yahoo_authorize_url",
        lambda uid: YahooAuthorizeResponse(authorization_url="https://y/auth"),
    )
    assert svc.gmail_authorize_url(user_id).authorization_url == "https://g/auth"
    assert svc.outlook_authorize_url(user_id).authorization_url == "https://o/auth"
    assert svc.yahoo_authorize_url(user_id).authorization_url == "https://y/auth"

    monkeypatch.setattr(
        inbox_module.inbox_mailbox_oauth,
        "complete_gmail_oauth",
        lambda session, repo, *, code, state: GmailOAuthCallbackResult(
            connector_type="gmail", email_address="g@x"
        ),
    )
    monkeypatch.setattr(
        inbox_module.inbox_mailbox_oauth,
        "complete_outlook_oauth",
        lambda session, repo, *, code, state: GmailOAuthCallbackResult(
            connector_type="outlook", email_address="o@x"
        ),
    )
    monkeypatch.setattr(
        inbox_module.inbox_mailbox_oauth,
        "complete_yahoo_oauth",
        lambda session, repo, *, code, state: GmailOAuthCallbackResult(
            connector_type="yahoo", email_address="y@x"
        ),
    )
    assert svc.complete_gmail_oauth(code="c", state="s").email_address == "g@x"
    assert svc.complete_outlook_oauth(code="c", state="s").email_address == "o@x"
    assert svc.complete_yahoo_oauth(code="c", state="s").email_address == "y@x"


def test_oauth_available_static_methods(monkeypatch) -> None:
    monkeypatch.setattr(inbox_module.inbox_mailbox_oauth, "gmail_oauth_available", lambda: True)
    monkeypatch.setattr(inbox_module.inbox_mailbox_oauth, "outlook_oauth_available", lambda: False)
    monkeypatch.setattr(inbox_module.inbox_mailbox_oauth, "yahoo_oauth_available", lambda: True)
    assert InboxService.gmail_oauth_available() is True
    assert InboxService.outlook_oauth_available() is False
    assert InboxService.yahoo_oauth_available() is True


def test_test_connection_uses_inline_config(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    result = ConnectionTestResult(imap_ok=True, smtp_ok=False, error="smtp down")
    with patch.object(inbox_module, "get_mailbox") as mock_get:
        mock_get.return_value.test_connection.return_value = result
        response = svc.test_connection(user_id, connector_type="imap_smtp", config=_sample_config())
    assert response.imap_ok is True
    assert response.smtp_ok is False
    assert response.error == "smtp down"


def test_test_connection_without_config_uses_resolved(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    result = ConnectionTestResult(imap_ok=True, smtp_ok=True)
    with patch.object(inbox_module, "get_mailbox") as mock_get:
        mock_get.return_value.test_connection.return_value = result
        response = svc.test_connection(user_id)
    assert response.imap_ok is True


def test_test_connection_no_credentials_raises(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_use_env_credentials", False)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    with pytest.raises(ValidationError):
        svc.test_connection(user_id)


def test_fetch_messages_delegates_to_connector(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    fetched = FetchResult(messages=[], max_uid=5)
    with patch.object(inbox_module, "get_mailbox") as mock_get:
        mock_get.return_value.fetch_messages.return_value = fetched
        result = svc.fetch_messages(user_id, since_uid=1, limit=10)
    assert result.max_uid == 5


def test_fetch_messages_no_credentials_raises(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_use_env_credentials", False)
    user_id = _user(db_session)
    with pytest.raises(ValidationError):
        InboxService(db_session).fetch_messages(user_id)


def test_send_message_delegates_to_connector(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    message = OutboundMessage(to=["a@x.com"], subject="Hi", body="Hello")
    with patch.object(inbox_module, "get_mailbox") as mock_get:
        mock_get.return_value.send_message.return_value = SendResult(status="sent")
        result = svc.send_message(user_id, message)
    assert result.status == "sent"


def test_send_message_no_credentials_raises(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_use_env_credentials", False)
    user_id = _user(db_session)
    with pytest.raises(ValidationError):
        InboxService(db_session).send_message(
            user_id, OutboundMessage(to=["a@x.com"], subject="s", body="b")
        )
