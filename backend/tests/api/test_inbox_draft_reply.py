"""API tests for inbox reply drafting."""

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.conftest import register_and_login


def test_draft_reply_endpoint_blocked_when_disabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    headers = register_and_login(client, "draft-disabled@example.com")
    resp = client.post(
        "/api/v1/inbox/draft-reply",
        headers=headers,
        json={"classification_id": 1},
    )
    assert resp.status_code == 400


def test_draft_reply_endpoint_persists_result(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "draft-ok@example.com")
    client.put(
        "/api/v1/profile",
        headers=headers,
        json={"full_name": "Alex Example", "answers": {"salary_expectations": "$140k"}},
    )
    classified = client.post(
        "/api/v1/inbox/classify",
        headers=headers,
        json={
            "message": {
                "uid": 21,
                "from_addr": "hr@company.com",
                "subject": "Salary question",
                "body_text": "What are your salary expectations?",
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
    body = drafted.json()
    assert body["status"] == "draft"
    assert body["classification_id"] == classification_id
    assert body["body_text"]

    listed = client.get("/api/v1/inbox/reply-drafts", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == body["id"]
