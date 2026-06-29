"""Regression tests for scraper SSRF protections."""

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def test_source_test_rejects_loopback_query_url(client: TestClient) -> None:
    headers = register_and_login(client, "ssrf-blocked@example.com")
    source = client.post(
        "/api/v1/sources",
        json={
            "name": "SSRF",
            "adapter_key": "generic_html",
            "default_config": {"item": ".job", "title": ".title"},
        },
        headers=headers,
    )
    assert source.status_code == 201
    source_id = source.json()["id"]

    resp = client.post(
        f"/api/v1/sources/{source_id}/test",
        json={"query_url": "http://127.0.0.1/internal"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert (
        "not allowed" in (body["error"] or "").lower()
        or "disallowed" in (body["error"] or "").lower()
    )
