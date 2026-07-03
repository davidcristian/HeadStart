"""API tests for the application pipeline."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.worker.tasks import apply_to_job_task
from tests.conftest import register_and_login


def _seed_job(client: TestClient, headers: dict[str, str]) -> int:
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
        external_id="pipe-job",
        title="Platform Engineer",
        company="Globex",
        location="Berlin",
        url="https://boards.greenhouse.io/acme/jobs/pipe-job",
    )
    with patch.object(PipelineService, "scrape", return_value=[posting]):
        client.post(f"/api/v1/searches/{search_id}/run", headers=headers)
    return client.get("/api/v1/jobs", headers=headers).json()[0]["id"]


def test_list_applications_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/applications").status_code == 401


def test_list_applications_includes_manually_applied_jobs(client: TestClient) -> None:
    headers = register_and_login(client, "pipeline-manual@example.com")
    job_id = _seed_job(client, headers)
    client.patch(f"/api/v1/jobs/{job_id}", json={"status": "applied"}, headers=headers)

    body = client.get("/api/v1/applications", headers=headers).json()
    assert len(body) == 1
    assert body[0]["job_id"] == job_id
    assert body[0]["pipeline_stage"] == "awaiting_reply"


def test_list_applications_shows_queued_apply(client: TestClient) -> None:
    headers = register_and_login(client, "pipeline-queued@example.com")
    job_id = _seed_job(client, headers)
    source_id = client.get("/api/v1/sources", headers=headers).json()[0]["id"]
    client.patch(f"/api/v1/sources/{source_id}", json={"auto_apply_enabled": True}, headers=headers)
    client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "resume_text": "CV",
        },
        headers=headers,
    )

    with patch.object(apply_to_job_task, "delay"):
        queued = client.post(f"/api/v1/jobs/{job_id}/apply", json={}, headers=headers)
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"

    body = client.get("/api/v1/applications", headers=headers).json()
    assert len(body) == 1
    assert body[0]["pipeline_stage"] == "queued"
    assert body[0]["latest_attempt"]["status"] == "queued"


def test_list_applications_filters_by_stage(client: TestClient) -> None:
    headers = register_and_login(client, "pipeline-filter@example.com")
    job_id = _seed_job(client, headers)
    client.patch(f"/api/v1/jobs/{job_id}", json={"status": "applied"}, headers=headers)
    client.patch(f"/api/v1/jobs/{job_id}", json={"status": "archived"}, headers=headers)

    archived = client.get("/api/v1/applications?stage=archived", headers=headers).json()
    awaiting = client.get("/api/v1/applications?stage=awaiting_reply", headers=headers).json()
    assert len(archived) == 1
    assert archived[0]["pipeline_stage"] == "archived"
    assert awaiting == []
