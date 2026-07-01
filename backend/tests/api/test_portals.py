"""Tests for curated portal catalog."""

from fastapi.testclient import TestClient


def test_portals_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/portals").status_code == 401


def test_portals_lists_curated_entries(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/portals", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) >= 20
    assert body["categories"] == ["big_tech", "unicorn", "ai"]
    stripe = next(item for item in body["items"] if item["id"] == "stripe")
    assert stripe["company_name"] == "Stripe"
    assert stripe["adapter_key"] == "greenhouse"
    assert stripe["supports_auto_apply"] is True
    assert stripe["allowed_on_plan"] is True
    assert stripe["already_added"] is False


def test_portals_filter_by_category(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/portals?category=ai", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items
    assert all(item["category"] == "ai" for item in items)
    assert any(item["id"] == "openai" for item in items)


def test_portals_search_query(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/portals?q=figma", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["company_name"] == "Figma"


def test_portals_marks_existing_source(client: TestClient, auth_headers: dict[str, str]) -> None:
    create = client.post(
        "/api/v1/sources",
        json={
            "name": "Stripe",
            "adapter_key": "greenhouse",
            "base_url": "https://boards.greenhouse.io/stripe",
            "default_config": {"board_token": "stripe", "company": "Stripe", "portal_id": "stripe"},
        },
        headers=auth_headers,
    )
    assert create.status_code == 201

    resp = client.get("/api/v1/portals", headers=auth_headers)
    stripe = next(item for item in resp.json()["items"] if item["id"] == "stripe")
    assert stripe["already_added"] is True
