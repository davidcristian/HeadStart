"""Tests for RSS feed API endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from tests.conftest import post_search_run, register_and_login


def _seed_job_via_api(client: TestClient, headers: dict[str, str]) -> None:
    source_id = client.post(
        "/api/v1/sources",
        json={"name": "ACME", "adapter_key": "greenhouse"},
        headers=headers,
    ).json()["id"]
    search_id = client.post(
        "/api/v1/searches",
        json={"name": "ACME SWE", "source_id": source_id, "interval_seconds": 60},
        headers=headers,
    ).json()["id"]
    posting = JobPosting(
        external_id="rss-job",
        title="Platform Engineer",
        company="ACME",
        location="Remote",
        url="https://acme.test/rss-job",
    )
    with patch.object(PipelineService, "scrape", return_value=[posting]):
        post_search_run(client, search_id, headers)


def test_feed_url_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/feed/url").status_code == 401


def test_feed_url_and_rss_round_trip(client: TestClient) -> None:
    headers = register_and_login(client, "rss-roundtrip@example.com")
    _seed_job_via_api(client, headers)

    feed = client.get("/api/v1/feed/url", headers=headers)
    assert feed.status_code == 200
    payload = feed.json()
    assert payload["url"].startswith("http://testserver/api/v1/feed/rss?token=")

    rss = client.get(payload["url"])
    assert rss.status_code == 200
    assert rss.headers["content-type"].startswith("application/rss+xml")
    assert "Platform Engineer" in rss.text
    assert "https://acme.test/rss-job" in rss.text


def test_rss_feed_rejects_invalid_token(client: TestClient) -> None:
    resp = client.get("/api/v1/feed/rss?token=not-a-valid-token")
    assert resp.status_code == 401


def test_rss_feed_rejects_missing_token(client: TestClient) -> None:
    resp = client.get("/api/v1/feed/rss")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing feed token."


def test_rss_feed_accepts_bearer_token(client: TestClient) -> None:
    headers = register_and_login(client, "rss-bearer@example.com")
    _seed_job_via_api(client, headers)
    token = client.get("/api/v1/feed/url", headers=headers).json()["token"]

    rss = client.get(
        "/api/v1/feed/rss",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rss.status_code == 200
    assert rss.headers["content-type"].startswith("application/rss+xml")
    assert "Platform Engineer" in rss.text


def test_rss_feed_query_token_wins_over_bearer(client: TestClient) -> None:
    headers = register_and_login(client, "rss-query-wins@example.com")
    token = client.get("/api/v1/feed/url", headers=headers).json()["token"]

    assert (
        client.get(
            f"/api/v1/feed/rss?token={token}",
            headers={"Authorization": "Bearer not-a-valid-token"},
        ).status_code
        == 200
    )


def test_rss_feed_rejects_non_bearer_authorization(client: TestClient) -> None:
    resp = client.get("/api/v1/feed/rss", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing feed token."


def test_rss_feed_rejects_empty_bearer(client: TestClient) -> None:
    resp = client.get("/api/v1/feed/rss", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing feed token."


def test_rotate_feed_url_invalidates_old_link(client: TestClient) -> None:
    headers = register_and_login(client, "rss-rotate@example.com")

    old_url = client.get("/api/v1/feed/url", headers=headers).json()["url"]
    new_url = client.post("/api/v1/feed/rotate", headers=headers).json()["url"]

    assert client.get(old_url).status_code == 401
    assert client.get(new_url).status_code == 200


def test_rss_feed_scopes_jobs_to_token_owner(client: TestClient) -> None:
    alice = register_and_login(client, "alice-rss@example.com")
    _seed_job_via_api(client, alice)
    bob = register_and_login(client, "bob-rss@example.com")
    bob_id = client.get("/api/v1/auth/me", headers=bob).json()["id"]
    assert (
        client.patch(
            f"/api/v1/admin/users/{bob_id}",
            json={"plan": "pro"},
            headers=alice,
        ).status_code
        == 200
    )

    feed_url = client.get("/api/v1/feed/url", headers=bob).json()["url"]
    rss = client.get(feed_url)

    assert rss.status_code == 200
    assert "Platform Engineer" not in rss.text


def test_rss_feed_supports_status_filter(client: TestClient) -> None:
    headers = register_and_login(client, "rss-filter@example.com")
    _seed_job_via_api(client, headers)
    job_id = client.get("/api/v1/jobs", headers=headers).json()[0]["id"]
    client.patch(f"/api/v1/jobs/{job_id}", json={"status": "applied"}, headers=headers)

    base_url = client.get("/api/v1/feed/url", headers=headers).json()["url"]
    filtered = f"{base_url}&status=applied"
    rss = client.get(filtered)

    assert rss.status_code == 200
    assert "Platform Engineer" in rss.text

    new_only = f"{base_url}&status=new"
    assert "Platform Engineer" not in client.get(new_only).text
