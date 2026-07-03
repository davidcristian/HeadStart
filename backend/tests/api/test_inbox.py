"""API tests for dev-only inbox mailbox endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.inbox.types import ConnectionTestResult, FetchResult, InboxMessage
from tests.conftest import register_and_login

MAILBOX_CONFIG = {
    "imap_host": "imap.example.com",
    "imap_user": "user@example.com",
    "imap_password": "imap-pass",
    "smtp_host": "smtp.example.com",
    "smtp_password": "smtp-pass",
    "smtp_from": "user@example.com",
}


def test_inbox_routes_blocked_when_disabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    headers = register_and_login(client, "inbox-disabled@example.com")
    resp = client.put(
        "/api/v1/inbox/credentials",
        headers=headers,
        json={"config": MAILBOX_CONFIG},
    )
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()


def test_mailbox_credential_crud(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "inbox-crud@example.com")

    create = client.put(
        "/api/v1/inbox/credentials",
        headers=headers,
        json={"config": MAILBOX_CONFIG},
    )
    assert create.status_code == 200
    body = create.json()
    assert body["imap_host"] == "imap.example.com"
    assert "imap_password" not in body

    read = client.get("/api/v1/inbox/credentials", headers=headers)
    assert read.status_code == 200
    assert read.json()["enabled"] is True

    delete = client.delete("/api/v1/inbox/credentials", headers=headers)
    assert delete.status_code == 204
    assert client.get("/api/v1/inbox/credentials", headers=headers).status_code == 404


def test_inbox_test_endpoint(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "inbox-test@example.com")
    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.test_connection") as mock_test:
        mock_test.return_value = ConnectionTestResult(imap_ok=True, smtp_ok=True)
        resp = client.post(
            "/api/v1/inbox/test",
            headers=headers,
            json={"config": MAILBOX_CONFIG},
        )
    assert resp.status_code == 200
    assert resp.json() == {"imap_ok": True, "smtp_ok": True, "error": None}


def test_inbox_fetch_messages(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "inbox-fetch@example.com")
    client.put("/api/v1/inbox/credentials", headers=headers, json={"config": MAILBOX_CONFIG})
    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.fetch_messages") as mock_fetch:
        mock_fetch.return_value = FetchResult(
            messages=[InboxMessage(uid=1, from_addr="hr@co.test", subject="Hello", body_text="Hi")],
            max_uid=1,
        )
        resp = client.get("/api/v1/inbox/messages", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_uid"] == 1
    assert body["messages"][0]["subject"] == "Hello"


def test_meta_includes_inbox_capabilities(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/meta", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "imap_smtp" in body["mailboxes"]
    assert "gmail" in body["mailboxes"]
    assert "outlook" in body["mailboxes"]
    assert "yahoo" in body["mailboxes"]
    assert "fastmail" in body["mailboxes"]
    assert body["inbox_agent_enabled"] is False


def test_outlook_authorize_requires_oauth_config(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "outlook_oauth_client_id", "")
    headers = register_and_login(client, "outlook-auth@example.com")
    resp = client.get("/api/v1/inbox/outlook/authorize", headers=headers)
    assert resp.status_code == 400


def test_gmail_authorize_requires_oauth_config(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "gmail_oauth_client_id", "")
    headers = register_and_login(client, "gmail-auth@example.com")
    resp = client.get("/api/v1/inbox/gmail/authorize", headers=headers)
    assert resp.status_code == 400


def test_yahoo_authorize_requires_oauth_config(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "yahoo_oauth_client_id", "")
    headers = register_and_login(client, "yahoo-auth@example.com")
    resp = client.get("/api/v1/inbox/yahoo/authorize", headers=headers)
    assert resp.status_code == 400


def test_upsert_fastmail_credentials(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "fastmail-crud@example.com")
    resp = client.put(
        "/api/v1/inbox/credentials",
        headers=headers,
        json={
            "connector_type": "fastmail",
            "config": {
                "email_address": "user@fastmail.test",
                "api_token": "fmu1-test-token",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["connector_type"] == "fastmail"
    assert body["email_address"] == "user@fastmail.test"
    assert "api_token" not in body


def test_upsert_rejects_non_manual_connector_type(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "gmail-upsert@example.com")
    resp = client.put(
        "/api/v1/inbox/credentials",
        headers=headers,
        json={"connector_type": "gmail", "config": MAILBOX_CONFIG},
    )
    assert resp.status_code == 400
