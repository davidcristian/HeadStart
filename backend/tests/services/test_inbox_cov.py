"""Coverage tests for InboxService connectors, OAuth wrappers, and resolution."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.inbox.credentials import encode_mailbox_config
from app.inbox.types import (
    ConnectionTestResult,
    FastmailMailboxConfig,
    FetchResult,
    GmailMailboxConfig,
    OutboundMessage,
    OutlookMailboxConfig,
    SendResult,
    YahooMailboxConfig,
)
from app.models.mailbox_credential import MailboxCredential
from app.models.user import User
from app.schemas.mailbox import (
    GmailAuthorizeResponse,
    GmailOAuthCallbackResult,
    MailboxConfig,
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


def _seed_oauth_credential(
    session: Session, user_id: int, *, connector_type: str, config
) -> MailboxCredential:
    credential = MailboxCredential(
        user_id=user_id,
        connector_type=connector_type,
        enabled=True,
        secret_ciphertext=encode_mailbox_config(config),
    )
    session.add(credential)
    session.flush()
    return credential


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


def test_resolve_context_refreshes_gmail(db_session: Session, monkeypatch) -> None:
    user_id = _user(db_session)
    config = GmailMailboxConfig(email_address="g@x", access_token="a", refresh_token="r")
    _seed_oauth_credential(db_session, user_id, connector_type="gmail", config=config)
    svc = InboxService(db_session)
    with patch.object(inbox_module, "ensure_fresh_gmail_config", return_value=config) as m:
        ctx = svc.resolve_context(user_id)
    assert ctx is not None
    assert ctx.connector_type == "gmail"
    m.assert_called_once()


def test_resolve_context_refreshes_outlook(db_session: Session, monkeypatch) -> None:
    user_id = _user(db_session)
    config = OutlookMailboxConfig(email_address="o@x", access_token="a", refresh_token="r")
    _seed_oauth_credential(db_session, user_id, connector_type="outlook", config=config)
    svc = InboxService(db_session)
    with patch.object(inbox_module, "ensure_fresh_outlook_config", return_value=config):
        ctx = svc.resolve_context(user_id)
    assert ctx is not None
    assert ctx.connector_type == "outlook"


def test_resolve_context_refreshes_yahoo(db_session: Session, monkeypatch) -> None:
    user_id = _user(db_session)
    config = YahooMailboxConfig(email_address="y@x", access_token="a", refresh_token="r")
    _seed_oauth_credential(db_session, user_id, connector_type="yahoo", config=config)
    svc = InboxService(db_session)
    with patch.object(inbox_module, "ensure_fresh_yahoo_config", return_value=config):
        ctx = svc.resolve_context(user_id)
    assert ctx is not None
    assert ctx.connector_type == "yahoo"


@pytest.mark.parametrize(
    ("connector_type", "decoded"),
    (
        ("gmail", OutlookMailboxConfig(email_address="o@x", access_token="a", refresh_token="r")),
        ("outlook", GmailMailboxConfig(email_address="g@x", access_token="a", refresh_token="r")),
        ("yahoo", GmailMailboxConfig(email_address="g@x", access_token="a", refresh_token="r")),
    ),
)
def test_resolve_context_rejects_mismatched_oauth_config(
    db_session: Session, connector_type, decoded
) -> None:
    # The stored connector_type selects the expected config class; a decode that returns a
    # different type (e.g. tampered ciphertext) must be rejected before use.
    user_id = _user(db_session)
    config = {
        "gmail": GmailMailboxConfig,
        "outlook": OutlookMailboxConfig,
        "yahoo": YahooMailboxConfig,
    }[connector_type](email_address="u@x", access_token="a", refresh_token="r")
    _seed_oauth_credential(db_session, user_id, connector_type=connector_type, config=config)
    svc = InboxService(db_session)
    with (
        patch.object(inbox_module, "decode_mailbox_config", return_value=decoded),
        pytest.raises(ValidationError),
    ):
        svc.resolve_context(user_id)


def test_resolve_context_returns_none_when_unconfigured(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_use_env_credentials", False)
    user_id = _user(db_session)
    assert InboxService(db_session).resolve_context(user_id) is None


def test_mailbox_user_email_from_read(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    assert svc.mailbox_user_email(user_id) == "user@example.com"


def test_mailbox_user_email_env_fallback(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_use_env_credentials", True)
    monkeypatch.setattr(settings, "inbox_imap_user", "env@example.com")
    user_id = _user(db_session)
    assert InboxService(db_session).mailbox_user_email(user_id) == "env@example.com"


def test_mailbox_user_email_empty_when_nothing_configured(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_use_env_credentials", False)
    monkeypatch.setattr(settings, "inbox_imap_user", "")
    user_id = _user(db_session)
    assert InboxService(db_session).mailbox_user_email(user_id) == ""


def test_config_for_export_present_and_absent(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    assert svc.config_for_export(user_id) is None
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    exported = svc.config_for_export(user_id)
    assert exported is not None


def test_validate_connector_type_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        InboxService._validate_connector_type("nonsense")


def test_context_from_config_builds_context() -> None:
    config = MailboxConfig(
        imap_host="h",
        imap_user="u",
        imap_password="p",
        smtp_host="s",
    )
    ctx = InboxService._context_from_config(3, "imap_smtp", config)
    assert ctx.connector_type == "imap_smtp"
    assert ctx.user_id == 3
