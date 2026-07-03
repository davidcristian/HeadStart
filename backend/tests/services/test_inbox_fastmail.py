"""Fastmail credential storage tests."""

import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt
from app.inbox.types import FastmailMailboxConfig
from app.models.mailbox_credential import MailboxCredential
from app.models.user import User
from app.schemas.mailbox import MailboxCredentialUpsert
from app.services.inbox import InboxService


def _user(session: Session, email: str = "fastmail@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user.id


def test_upsert_fastmail_stores_encrypted_token(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxService(db_session)
    data = MailboxCredentialUpsert(
        connector_type="fastmail",
        enabled=True,
        config=FastmailMailboxConfig(
            email_address="user@fastmail.test",
            api_token="fmu1-secret-token",
        ),
    )
    read = svc.upsert(user_id, data)
    assert read.connector_type == "fastmail"
    assert read.email_address == "user@fastmail.test"
    row = db_session.query(MailboxCredential).filter_by(user_id=user_id).one()
    payload = json.loads(decrypt(row.secret_ciphertext))
    assert payload["api_token"] == "fmu1-secret-token"
    assert "fmu1-secret-token" not in row.secret_ciphertext
