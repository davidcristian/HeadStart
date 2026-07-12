"""Inbox query-param bounds: API-04 list routes + API-07 /messages."""

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.conftest import register_and_login


def test_classifications_limit_out_of_bounds_returns_422(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "list-params-class@example.com")

    too_high = client.get("/api/v1/inbox/classifications?limit=201", headers=headers)
    assert too_high.status_code == 422

    too_low = client.get("/api/v1/inbox/classifications?limit=0", headers=headers)
    assert too_low.status_code == 422

    negative = client.get("/api/v1/inbox/classifications?limit=-1", headers=headers)
    assert negative.status_code == 422


def test_reply_drafts_seen_job_id_and_limit_bounds_return_422(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "list-params-drafts@example.com")

    bad_seen = client.get("/api/v1/inbox/reply-drafts?seen_job_id=0", headers=headers)
    assert bad_seen.status_code == 422

    bad_limit = client.get("/api/v1/inbox/reply-drafts?limit=201", headers=headers)
    assert bad_limit.status_code == 422


def test_reply_send_logs_limit_out_of_bounds_returns_422(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "list-params-logs@example.com")

    too_high = client.get("/api/v1/inbox/reply-send-logs?limit=201", headers=headers)
    assert too_high.status_code == 422

    too_low = client.get("/api/v1/inbox/reply-send-logs?limit=0", headers=headers)
    assert too_low.status_code == 422


def test_messages_since_uid_and_limit_bounds_return_422(client: TestClient, monkeypatch) -> None:
    """API-07: /messages uses Query(ge,le) so bad params 422 before the service."""
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    headers = register_and_login(client, "list-params-messages@example.com")

    bad_since = client.get("/api/v1/inbox/messages?since_uid=0", headers=headers)
    assert bad_since.status_code == 422

    negative_since = client.get("/api/v1/inbox/messages?since_uid=-1", headers=headers)
    assert negative_since.status_code == 422

    too_high = client.get("/api/v1/inbox/messages?limit=101", headers=headers)
    assert too_high.status_code == 422

    too_low = client.get("/api/v1/inbox/messages?limit=0", headers=headers)
    assert too_low.status_code == 422

    negative_limit = client.get("/api/v1/inbox/messages?limit=-1", headers=headers)
    assert negative_limit.status_code == 422
