"""Tests for plan limit enforcement."""

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def _free_user_headers(client: TestClient, email: str) -> dict[str, str]:
    """Register a non-admin user (second+ account) on the free plan."""
    register_and_login(client, "bootstrap-admin@example.com")
    return register_and_login(client, email)


def _create_source(client: TestClient, headers: dict[str, str], name: str) -> int:
    resp = client.post(
        "/api/v1/sources",
        json={"name": name, "adapter_key": "greenhouse"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_free_plan_blocks_fourth_source(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-sources@example.com")
    for index in range(3):
        _create_source(client, headers, f"Source {index + 1}")

    blocked = client.post(
        "/api/v1/sources",
        json={"name": "One too many", "adapter_key": "greenhouse"},
        headers=headers,
    )
    assert blocked.status_code == 402
    body = blocked.json()
    assert body["code"] == "source_limit"
    assert body["limit"] == 3
    assert "Free plan" in body["detail"]


def test_free_plan_blocks_premium_scraper(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-scraper@example.com")
    resp = client.post(
        "/api/v1/sources",
        json={"name": "Indeed", "adapter_key": "indeed"},
        headers=headers,
    )
    assert resp.status_code == 402
    assert resp.json()["code"] == "premium_scraper"


def test_free_plan_blocks_webhook_target(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-webhook@example.com")
    resp = client.post(
        "/api/v1/targets",
        json={
            "name": "Hook",
            "type": "webhook",
            "config": {"webhook_url": "https://example.com/hook"},
        },
        headers=headers,
    )
    assert resp.status_code == 402
    assert resp.json()["code"] == "premium_notifier"


def test_free_plan_blocks_second_target(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-targets@example.com")
    first = client.post(
        "/api/v1/targets",
        json={"name": "Phone", "type": "ntfy", "config": {"topic": "abc"}},
        headers=headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/targets",
        json={"name": "Email", "type": "email", "config": {"to": "me@example.com"}},
        headers=headers,
    )
    assert second.status_code == 402
    assert second.json()["code"] == "target_limit"


def test_free_plan_blocks_digest_search(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-digest@example.com")
    source_id = _create_source(client, headers, "ACME")
    resp = client.post(
        "/api/v1/searches",
        json={
            "name": "Digest watch",
            "source_id": source_id,
            "interval_seconds": 60,
            "notification_mode": "digest",
        },
        headers=headers,
    )
    assert resp.status_code == 402
    assert resp.json()["code"] == "digest_mode"


def test_free_plan_blocks_site_credentials(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-creds@example.com")
    source_id = _create_source(client, headers, "ACME")
    resp = client.post(
        "/api/v1/credentials",
        json={"source_id": source_id, "name": "Session", "cookies": {"sid": "x"}},
        headers=headers,
    )
    assert resp.status_code == 402
    assert resp.json()["code"] == "site_credentials"


def test_free_plan_blocks_rss_feed_url(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-rss@example.com")
    resp = client.get("/api/v1/feed/url", headers=headers)
    assert resp.status_code == 402
    assert resp.json()["code"] == "rss_feed"


def test_free_plan_blocks_portal_search(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-portal@example.com")
    resp = client.post(
        "/api/v1/portals/search",
        json={"keywords": "engineer", "portal_ids": ["stripe"]},
        headers=headers,
    )
    assert resp.status_code == 402
    assert resp.json()["code"] == "portal_search"


def test_meta_includes_plan_snapshot(client: TestClient) -> None:
    headers = _free_user_headers(client, "limits-meta@example.com")
    resp = client.get("/api/v1/meta", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["plan"] == "free"
    assert body["plan"]["show_ads"] is True
    assert body["plan"]["limits"]["max_sources"] == 3
    assert "indeed" not in body["scrapers"]
    assert "webhook" not in body["notifiers"]
    assert "greenhouse" in body["scrapers"]
    assert body["ads"]["external_slot_url"] is None


def test_meta_hides_ads_for_pro_plan(client: TestClient) -> None:
    admin = register_and_login(client, "ads-admin@example.com")
    user_headers = register_and_login(client, "ads-user@example.com")
    user_id = client.get("/api/v1/auth/me", headers=user_headers).json()["id"]
    patched = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"plan": "pro"},
        headers=admin,
    )
    assert patched.status_code == 200

    resp = client.get("/api/v1/meta", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["plan"]["show_ads"] is False


def test_admin_can_set_user_plan(client: TestClient) -> None:
    admin = register_and_login(client, "plan-admin@example.com")
    user_headers = register_and_login(client, "plan-user@example.com")
    user_id = client.get("/api/v1/auth/me", headers=user_headers).json()["id"]

    patched = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"plan": "pro"},
        headers=admin,
    )
    assert patched.status_code == 200
    assert patched.json()["plan"] == "pro"

    me = client.get("/api/v1/auth/me", headers=user_headers).json()
    assert me["plan"] == "pro"

    # Pro user can use RSS
    assert client.get("/api/v1/feed/url", headers=user_headers).status_code == 200
