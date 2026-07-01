"""Route tests for job auto-apply."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from tests.conftest import register_and_login


def _seed_greenhouse_job_via_api(client: TestClient, headers: dict[str, str]) -> int:
    source_id = client.post(
        "/api/v1/sources",
        json={
            "name": "ACME",
            "adapter_key": "greenhouse",
            "default_config": {"board_token": "acme", "job_board_api_key": "test-key"},
        },
        headers=headers,
    ).json()["id"]
    search_id = client.post(
        "/api/v1/searches",
        json={"name": "ACME SWE", "source_id": source_id, "interval_seconds": 60},
        headers=headers,
    ).json()["id"]
    posting = JobPosting(
        external_id="5501001",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/5501001",
    )
    with patch.object(PipelineService, "scrape", return_value=[posting]):
        client.post(f"/api/v1/searches/{search_id}/run", headers=headers)
    return client.get("/api/v1/jobs", headers=headers).json()[0]["id"]


def test_apply_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/jobs/1/apply", json={}).status_code == 401


def test_apply_dry_run_returns_payload(client: TestClient) -> None:
    headers = register_and_login(client, "apply-dry@example.com")
    job_id = _seed_greenhouse_job_via_api(client, headers)

    client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "resume_text": "CV",
        },
        headers=headers,
    )

    resp = client.post(
        f"/api/v1/jobs/{job_id}/apply",
        json={"dry_run": True, "cover_letter": "Dear ACME team"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["payload"]["email"] == "ada@example.com"
    assert body["payload"]["cover_letter_text"] == "Dear ACME team"
    assert body["job"] is None

    listed = client.get("/api/v1/jobs", headers=headers).json()
    assert listed[0]["status"] == "new"


def test_apply_without_profile_returns_400(client: TestClient) -> None:
    headers = register_and_login(client, "apply-noprofile@example.com")
    job_id = _seed_greenhouse_job_via_api(client, headers)

    resp = client.post(f"/api/v1/jobs/{job_id}/apply", json={"dry_run": True}, headers=headers)
    assert resp.status_code == 400
    assert "profile" in resp.json()["detail"].lower()


def test_apply_scopes_jobs_by_user(client: TestClient) -> None:
    alice = register_and_login(client, "apply-alice@example.com")
    job_id = _seed_greenhouse_job_via_api(client, alice)
    bob = register_and_login(client, "apply-bob@example.com")
    client.put(
        "/api/v1/profile",
        json={"full_name": "Bob Builder", "email": "bob@example.com"},
        headers=bob,
    )

    assert (
        client.post(f"/api/v1/jobs/{job_id}/apply", json={"dry_run": True}, headers=bob).status_code
        == 404
    )
