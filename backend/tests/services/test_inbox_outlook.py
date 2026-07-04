"""Outlook credential storage and OAuth completion tests."""

import json

import respx
from httpx import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt
from app.inbox.outlook_oauth import create_outlook_oauth_state
from app.models.mailbox_credential import MailboxCredential
from app.models.user import User
from app.services.inbox import InboxService


def _user(session: Session, email: str = "outlook@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user.id


@respx.mock
def test_complete_outlook_oauth_stores_encrypted_tokens(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "outlook_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "outlook_oauth_client_secret", "secret")
    monkeypatch.setattr(settings, "outlook_oauth_redirect_uri", "http://localhost/callback")
    user_id = _user(db_session)
    issued = create_outlook_oauth_state(user_id)
    respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
            },
        )
    )
    respx.get("https://graph.microsoft.com/v1.0/me").mock(
        return_value=Response(200, json={"mail": "user@outlook.test"})
    )
    svc = InboxService(db_session)
    result = svc.complete_outlook_oauth(
        code="auth-code", state=issued.state, oauth_nonce=issued.nonce
    )
    assert result.connector_type == "outlook"
    assert result.email_address == "user@outlook.test"
    read = svc.get_read(user_id)
    assert read.connector_type == "outlook"
    assert read.email_address == "user@outlook.test"
    row = db_session.query(MailboxCredential).filter_by(user_id=user_id).one()
    payload = json.loads(decrypt(row.secret_ciphertext))
    assert payload["refresh_token"] == "refresh-token"
    assert "refresh-token" not in row.secret_ciphertext
