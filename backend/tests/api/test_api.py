from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.pipeline import PipelineService, RunResult
from tests.conftest import register_and_login


def test_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_meta_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/meta").status_code == 401


def test_meta_lists_capabilities(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/meta", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "greenhouse" in body["scrapers"]
    assert "generic_html" in body["scrapers"]
    assert "ntfy" in body["notifiers"]
    assert "email" in body["notifiers"]
    assert "slack" in body["notifiers"]


def test_reads_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/sources").status_code == 401
    assert client.get("/api/v1/searches").status_code == 401
    assert client.get("/api/v1/jobs").status_code == 401


def test_create_source_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/sources", json={"name": "X", "adapter_key": "greenhouse"})
    assert resp.status_code == 401


def test_source_crud(client: TestClient, auth_headers: dict[str, str]) -> None:
    create = client.post(
        "/api/v1/sources",
        json={"name": "ACME", "adapter_key": "greenhouse", "base_url": "https://acme.test"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    source_id = create.json()["id"]

    assert client.get(f"/api/v1/sources/{source_id}", headers=auth_headers).status_code == 200
    assert len(client.get("/api/v1/sources", headers=auth_headers).json()) == 1

    patched = client.patch(
        f"/api/v1/sources/{source_id}", json={"enabled": False}, headers=auth_headers
    )
    assert patched.json()["enabled"] is False

    assert client.delete(f"/api/v1/sources/{source_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/sources/{source_id}", headers=auth_headers).status_code == 404


def test_create_source_rejects_unknown_adapter(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/sources",
        json={"name": "X", "adapter_key": "does-not-exist"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_search_lifecycle(client: TestClient, auth_headers: dict[str, str]) -> None:
    source_id = client.post(
        "/api/v1/sources",
        json={"name": "ACME", "adapter_key": "greenhouse"},
        headers=auth_headers,
    ).json()["id"]
    target_id = client.post(
        "/api/v1/targets",
        json={"name": "Phone", "type": "ntfy", "config": {"topic": "abc"}},
        headers=auth_headers,
    ).json()["id"]

    created = client.post(
        "/api/v1/searches",
        json={
            "name": "ACME SWE",
            "source_id": source_id,
            "target_id": target_id,
            "config": {"board_token": "acme"},
            "interval_seconds": 60,
        },
        headers=auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["last_error"] is None
    assert body["recent_delivery_failures"] == []
    search_id = body["id"]

    with patch.object(
        PipelineService,
        "run",
        return_value=RunResult(search_id=search_id, found=0, new=0, notified=0, failed=0),
    ):
        run = client.post(f"/api/v1/searches/{search_id}/run", headers=auth_headers)
    assert run.status_code == 200
    assert run.json()["search_id"] == search_id


def test_source_test_returns_sample(client: TestClient, auth_headers: dict[str, str]) -> None:
    source_id = client.post(
        "/api/v1/sources",
        json={
            "name": "ACME",
            "adapter_key": "greenhouse",
            "base_url": "https://boards.example.test/acme",
            "default_config": {"board_token": "acme"},
        },
        headers=auth_headers,
    ).json()["id"]

    with patch.object(
        PipelineService,
        "scrape",
        return_value=[],
    ):
        resp = client.post(f"/api/v1/sources/{source_id}/test", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["found"] == 0
    assert body["sample"] == []


def test_search_rejects_missing_source(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/searches",
        json={"name": "bad", "source_id": 999},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_users_cannot_see_each_others_sources(client: TestClient) -> None:
    alice = register_and_login(client, "alice@example.com")
    bob = register_and_login(client, "bob@example.com")

    source_id = client.post(
        "/api/v1/sources",
        json={"name": "Alice Co", "adapter_key": "greenhouse"},
        headers=alice,
    ).json()["id"]

    # Alice sees it; Bob does not.
    assert len(client.get("/api/v1/sources", headers=alice).json()) == 1
    assert client.get("/api/v1/sources", headers=bob).json() == []

    # Bob cannot fetch, patch, or delete Alice's source.
    assert client.get(f"/api/v1/sources/{source_id}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/api/v1/sources/{source_id}", json={"enabled": False}, headers=bob
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/sources/{source_id}", headers=bob).status_code == 404
