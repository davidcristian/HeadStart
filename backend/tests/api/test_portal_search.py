"""Tests for cross-portal search and subscribe."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from tests.conftest import register_and_login


def _pro_user_headers(client: TestClient, email: str) -> dict[str, str]:
    admin = register_and_login(client, f"admin-{email}")
    user_headers = register_and_login(client, email)
    user_id = client.get("/api/v1/auth/me", headers=user_headers).json()["id"]
    patched = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"plan": "pro"},
        headers=admin,
    )
    assert patched.status_code == 200
    return user_headers


def _posting(company: str, title: str, portal_suffix: str) -> JobPosting:
    return JobPosting(
        external_id=f"{portal_suffix}-1",
        title=title,
        company=company,
        location="Remote",
        url=f"https://example.com/{portal_suffix}",
    )


def test_portal_search_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/portals/search", json={"keywords": "engineer"})
    assert resp.status_code == 401


def test_free_plan_blocks_portal_search(client: TestClient) -> None:
    register_and_login(client, "bootstrap@example.com")
    headers = register_and_login(client, "free-portal@example.com")
    resp = client.post(
        "/api/v1/portals/search",
        json={"keywords": "engineer", "portal_ids": ["stripe"]},
        headers=headers,
    )
    assert resp.status_code == 402
    assert resp.json()["code"] == "portal_search"


def test_portal_search_returns_matches(client: TestClient) -> None:
    headers = _pro_user_headers(client, "portal-search@example.com")

    def fake_scrape(self, **kwargs: object) -> list[JobPosting]:
        config = kwargs.get("config") or {}
        company = str(config.get("company") or "ACME")
        return [_posting(company, "Software Engineer", company.casefold())]

    with patch.object(PipelineService, "scrape", fake_scrape):
        resp = client.post(
            "/api/v1/portals/search",
            json={"keywords": "engineer", "portal_ids": ["stripe", "figma"]},
            headers=headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["portals_searched"] == 2
    assert body["portals_failed"] == 0
    assert len(body["items"]) == 2
    companies = {item["company_name"] for item in body["items"]}
    assert companies == {"Stripe", "Figma"}


def test_portal_search_surfaces_per_portal_errors(client: TestClient) -> None:
    headers = _pro_user_headers(client, "portal-errors@example.com")
    calls = {"count": 0}

    def flaky_scrape(self, **kwargs: object) -> list[JobPosting]:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("board unavailable")
        return [_posting("Figma", "Designer", "figma")]

    with patch.object(PipelineService, "scrape", flaky_scrape):
        resp = client.post(
            "/api/v1/portals/search",
            json={"keywords": "design", "portal_ids": ["stripe", "figma"]},
            headers=headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["portals_failed"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["portal_id"] == "stripe"
    assert len(body["items"]) == 1


def test_portal_subscribe_creates_source_and_search(client: TestClient) -> None:
    headers = _pro_user_headers(client, "portal-subscribe@example.com")
    target_id = client.post(
        "/api/v1/targets",
        json={"name": "Phone", "type": "ntfy", "config": {"topic": "jobs-a1b2c3d4e5f67890"}},
        headers=headers,
    ).json()["id"]

    resp = client.post(
        "/api/v1/portals/subscribe",
        json={
            "portal_ids": ["stripe"],
            "keywords": "payments",
            "target_id": target_id,
            "interval_seconds": 600,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources_created"] == 1
    assert body["searches_created"] == 1
    assert len(body["search_ids"]) == 1

    sources = client.get("/api/v1/sources", headers=headers).json()
    assert any(s["name"] == "Stripe" for s in sources)

    searches = client.get("/api/v1/searches", headers=headers).json()
    stripe_search = next(s for s in searches if s["source_id"] == sources[0]["id"])
    assert stripe_search["filters"]["keywords_include"] == "payments"


def test_portal_subscribe_skips_duplicate_search(client: TestClient) -> None:
    headers = _pro_user_headers(client, "portal-dup@example.com")
    target_id = client.post(
        "/api/v1/targets",
        json={"name": "Phone", "type": "ntfy", "config": {"topic": "jobs-a1b2c3d4e5f67890"}},
        headers=headers,
    ).json()["id"]

    payload = {
        "portal_ids": ["stripe"],
        "keywords": "platform",
        "target_id": target_id,
    }
    first = client.post("/api/v1/portals/subscribe", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["searches_created"] == 1

    second = client.post("/api/v1/portals/subscribe", json=payload, headers=headers)
    assert second.status_code == 200
    body = second.json()
    assert body["searches_created"] == 0
    assert body["skipped_portal_ids"] == ["stripe"]
