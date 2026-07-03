"""API tests for inbox folder routing."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.inbox.types import MoveResult
from tests.conftest import register_and_login

MAILBOX_CONFIG = {
    "imap_host": "imap.example.com",
    "imap_user": "user@example.com",
    "imap_password": "imap-pass",
    "smtp_host": "smtp.example.com",
    "smtp_password": "smtp-pass",
    "smtp_from": "user@example.com",
}


def test_routing_config_round_trip(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "routing-config@example.com")
    client.put("/api/v1/inbox/credentials", headers=headers, json={"config": MAILBOX_CONFIG})

    defaults = client.get("/api/v1/inbox/routing", headers=headers)
    assert defaults.status_code == 200
    body = defaults.json()
    assert body["enabled"] is False
    assert body["label_folders"]["rejection"] == "HeadStart/Rejections"

    updated = client.put(
        "/api/v1/inbox/routing",
        headers=headers,
        json={"enabled": True, "label_folders": {"general": "Custom/General"}},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["label_folders"]["general"] == "Custom/General"


def test_classify_auto_routes_when_enabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "routing-classify@example.com")
    client.put("/api/v1/inbox/credentials", headers=headers, json={"config": MAILBOX_CONFIG})
    client.put("/api/v1/inbox/routing", headers=headers, json={"enabled": True})

    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.move_message") as mock_move:
        mock_move.return_value = MoveResult(status="moved", destination="HeadStart/Rejections")
        resp = client.post(
            "/api/v1/inbox/classify",
            headers=headers,
            json={
                "message": {
                    "uid": 21,
                    "subject": "Unfortunately",
                    "body_text": "We will not be moving forward with your application.",
                }
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "rejection"
    assert body["routing_status"] == "moved"
    assert body["routed_to"] == "HeadStart/Rejections"
    mock_move.assert_called_once()


def test_route_endpoint_moves_classified_message(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "routing-route@example.com")
    client.put("/api/v1/inbox/credentials", headers=headers, json={"config": MAILBOX_CONFIG})
    client.put(
        "/api/v1/inbox/routing",
        headers=headers,
        json={"enabled": True, "auto_route_on_classify": False},
    )

    classify = client.post(
        "/api/v1/inbox/classify",
        headers=headers,
        json={
            "message": {
                "uid": 33,
                "subject": "Update",
                "body_text": "Thanks for applying — we will review your profile.",
            }
        },
    )
    assert classify.status_code == 200
    classification_id = classify.json()["id"]

    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.move_message") as mock_move:
        mock_move.return_value = MoveResult(status="moved", destination="HeadStart/General")
        route = client.post(
            "/api/v1/inbox/route",
            headers=headers,
            json={"classification_id": classification_id},
        )

    assert route.status_code == 200
    assert route.json()["routing_status"] == "moved"
    assert mock_move.call_count >= 1
