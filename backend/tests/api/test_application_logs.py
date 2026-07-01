"""Route tests for application log audit trail."""

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


def test_application_logs_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/application-logs").status_code == 401


def test_application_logs_list_after_dry_run(client: TestClient) -> None:
    headers = register_and_login(client, "apply-log@example.com")
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

    client.post(f"/api/v1/jobs/{job_id}/apply", json={"dry_run": True}, headers=headers)

    resp = client.get("/api/v1/application-logs", headers=headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) == 1
    assert logs[0]["status"] == "dry_run"
    assert logs[0]["dry_run"] is True
    assert logs[0]["job_title"] == "Senior Engineer"
    assert logs[0]["seen_job_id"] == job_id


def test_apply_live_without_opt_in_returns_400(client: TestClient) -> None:
    headers = register_and_login(client, "apply-noopt@example.com")
    job_id = _seed_greenhouse_job_via_api(client, headers)
    client.put(
        "/api/v1/profile",
        json={"full_name": "Ada Lovelace", "email": "ada@example.com", "resume_text": "CV"},
        headers=headers,
    )

    resp = client.post(f"/api/v1/jobs/{job_id}/apply", json={"dry_run": False}, headers=headers)
    assert resp.status_code == 400
    assert "auto-apply" in resp.json()["detail"].lower()


def test_source_auto_apply_opt_in(client: TestClient) -> None:
    headers = register_and_login(client, "apply-optin@example.com")
    source_id = client.post(
        "/api/v1/sources",
        json={
            "name": "ACME",
            "adapter_key": "greenhouse",
            "default_config": {"board_token": "acme"},
        },
        headers=headers,
    ).json()["id"]

    source = client.get(f"/api/v1/sources/{source_id}", headers=headers).json()
    assert source["auto_apply_enabled"] is False

    resp = client.patch(
        f"/api/v1/sources/{source_id}",
        json={"auto_apply_enabled": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["auto_apply_enabled"] is True

    generic_id = client.post(
        "/api/v1/sources",
        json={"name": "Custom", "adapter_key": "generic_html"},
        headers=headers,
    ).json()["id"]
    bad = client.patch(
        f"/api/v1/sources/{generic_id}",
        json={"auto_apply_enabled": True},
        headers=headers,
    )
    assert bad.status_code == 400
