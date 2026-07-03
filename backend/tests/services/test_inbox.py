"""Unit tests for inbox credential storage and resolution."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.mailbox_credential import MailboxCredential
from app.models.user import User
from app.schemas.mailbox import MailboxConfig, MailboxCredentialUpsert
from app.services.inbox import InboxNotEnabledError, InboxService


def _user(session: Session, email: str = "inbox@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user.id


def _sample_config() -> MailboxConfig:
    return MailboxConfig(
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="imap-pass",
        smtp_host="smtp.example.com",
        smtp_password="smtp-pass",
        smtp_from="user@example.com",
    )


def test_upsert_encrypts_passwords(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    read = svc.upsert(
        user_id,
        MailboxCredentialUpsert(config=_sample_config()),
    )
    assert read.imap_host == "imap.example.com"
    assert read.imap_user == "user@example.com"
    row = db_session.get(MailboxCredential, read.id)
    assert row is not None
    assert "imap-pass" not in row.secret_ciphertext


def test_resolve_context_uses_enabled_credential(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    ctx = svc.resolve_context(user_id)
    assert ctx is not None
    assert ctx.config.imap_password == "imap-pass"


def test_disabled_credential_falls_back_to_env(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_use_env_credentials", True)
    monkeypatch.setattr(settings, "inbox_imap_host", "env-imap.example.com")
    monkeypatch.setattr(settings, "inbox_imap_user", "env@example.com")
    monkeypatch.setattr(settings, "inbox_imap_password", "env-pass")
    monkeypatch.setattr(settings, "inbox_smtp_host", "env-smtp.example.com")
    user_id = _user(db_session)
    svc = InboxService(db_session)
    read = svc.upsert(
        user_id,
        MailboxCredentialUpsert(enabled=False, config=_sample_config()),
    )
    assert read.enabled is False
    ctx = svc.resolve_context(user_id)
    assert ctx is not None
    assert ctx.config.imap_host == "env-imap.example.com"


def test_require_enabled_raises_when_disabled(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    svc = InboxService(db_session)
    try:
        svc.require_enabled()
        raised = False
    except InboxNotEnabledError:
        raised = True
    assert raised


def test_delete_removes_credential(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    svc.upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    svc.delete(user_id)
    try:
        svc.get_read(user_id)
        raised = False
    except NotFoundError:
        raised = True
    assert raised
