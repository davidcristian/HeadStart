"""API tests for inbox reply send audit logs."""

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.conftest import register_and_login


def test_reply_send_logs_blocked_when_inbox_disabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    headers = register_and_login(client, "send-log-disabled@example.com")
    resp = client.get("/api/v1/inbox/reply-send-logs", headers=headers)
    assert resp.status_code == 400


def test_reply_send_logs_lists_queue_audit_rows(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "send-log-ok@example.com")
    client.put(
        "/api/v1/profile",
        headers=headers,
        json={"full_name": "Alex Example", "answers": {"availability": "Next week"}},
    )
    client.put(
        "/api/v1/inbox/credentials",
        headers=headers,
        json={
            "config": {
                "imap_host": "imap.example.com",
                "imap_user": "alex@example.com",
                "imap_password": "secret",
                "smtp_host": "smtp.example.com",
                "smtp_user": "alex@example.com",
                "smtp_password": "secret",
            }
        },
    )
    client.put(
        "/api/v1/inbox/routing",
        headers=headers,
        json={"auto_reply_enabled": True},
    )
    classified = client.post(
        "/api/v1/inbox/classify",
        headers=headers,
        json={
            "message": {
                "uid": 31,
                "from_addr": "hr@company.com",
                "subject": "Availability",
                "body_text": "When can you interview?",
            }
        },
    )
    assert classified.status_code == 200
    classification_id = classified.json()["id"]

    drafted = client.post(
        "/api/v1/inbox/draft-reply",
        headers=headers,
        json={"classification_id": classification_id},
    )
    assert drafted.status_code == 200

    listed = client.get("/api/v1/inbox/reply-send-logs", headers=headers)
    assert listed.status_code == 200
    payload = listed.json()
    assert len(payload) >= 1
    assert payload[0]["outcome"] == "queued"
    assert payload[0]["inbox_reply_draft_id"] == drafted.json()["id"]
