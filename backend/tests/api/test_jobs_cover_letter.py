"""Route tests for cover-letter generation (async queue)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.worker.tasks import generate_cover_letter_task
from tests.conftest import post_search_run, register_and_login


def _seed_job(client: TestClient, headers: dict[str, str]) -> int:
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
        summary="Matches your search: mentions python.",
    )
    with patch.object(PipelineService, "scrape", return_value=[posting]):
        post_search_run(client, search_id, headers)
    return client.get("/api/v1/jobs", headers=headers).json()[0]["id"]


def test_generate_cover_letter_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/jobs/1/generate-cover-letter").status_code == 401


def test_generate_cover_letter_requires_profile(client: TestClient) -> None:
    headers = register_and_login(client, "cover-no-profile@example.com")
    job_id = _seed_job(client, headers)

    resp = client.post(f"/api/v1/jobs/{job_id}/generate-cover-letter", headers=headers)
    assert resp.status_code == 400
    assert "application profile" in resp.json()["detail"].lower()


def test_generate_cover_letter_queues(client: TestClient) -> None:
    headers = register_and_login(client, "cover-heuristic@example.com")
    job_id = _seed_job(client, headers)
    client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "cover_letter_template": "Dear {company} team, I am excited about {job_title}.",
            "skills": ["Python"],
        },
        headers=headers,
    )

    with patch.object(generate_cover_letter_task, "delay") as mock_delay:
        resp = client.post(f"/api/v1/jobs/{job_id}/generate-cover-letter", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["kind"] == "cover_letter"
    assert body["id"] > 0
    mock_delay.assert_called_once()
