"""API tests for inbox email classification."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.inbox.types import InboxMessage
from tests.conftest import register_and_login

MAILBOX_CONFIG = {
    "imap_host": "imap.example.com",
    "imap_user": "user@example.com",
    "imap_password": "imap-pass",
    "smtp_host": "smtp.example.com",
    "smtp_password": "smtp-pass",
    "smtp_from": "user@example.com",
}


def test_classify_endpoint_blocked_when_disabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    headers = register_and_login(client, "classify-disabled@example.com")
    resp = client.post(
        "/api/v1/inbox/classify",
        headers=headers,
        json={"message": {"uid": 1, "subject": "Hi", "body_text": "Hello"}},
    )
    assert resp.status_code == 400


def test_classify_endpoint_persists_result(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "classify-ok@example.com")
    resp = client.post(
        "/api/v1/inbox/classify",
        headers=headers,
        json={
            "message": {
                "uid": 11,
                "from_addr": "hr@company.com",
                "subject": "Interview",
                "body_text": "Please schedule a phone screen using Calendly.",
            }
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "interview_request"
    assert body["message_uid"] == 11

    listed = client.get("/api/v1/inbox/classifications", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["label"] == "interview_request"


def test_classify_by_uid_fetches_from_mailbox(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "classify-uid@example.com")
    client.put("/api/v1/inbox/credentials", headers=headers, json={"config": MAILBOX_CONFIG})
    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.fetch_messages") as mock_fetch:
        from app.inbox.types import FetchResult

        mock_fetch.return_value = FetchResult(
            messages=[
                InboxMessage(
                    uid=55,
                    from_addr="noreply@company.com",
                    subject="Rejection",
                    body_text="Unfortunately we chose other candidates.",
                )
            ],
            max_uid=55,
        )
        resp = client.post("/api/v1/inbox/classify", headers=headers, json={"uid": 55})
    assert resp.status_code == 200
    assert resp.json()["label"] == "rejection"


def test_classify_rejects_overlong_body_text(client: TestClient, monkeypatch) -> None:
    """INB-14: client-supplied InboxMessage body_text is bounded (HTTP 422)."""
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "classify-bounds@example.com")
    resp = client.post(
        "/api/v1/inbox/classify",
        headers=headers,
        json={
            "message": {
                "uid": 1,
                "subject": "Hi",
                "body_text": "x" * 100_001,
            }
        },
    )
    assert resp.status_code == 422
