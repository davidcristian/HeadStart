"""Route tests for async document generation."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.worker.tasks import generate_cover_letter_task, generate_resume_task
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


def _put_profile(client: TestClient, headers: dict[str, str]) -> None:
    client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "skills": ["Python"],
            "cover_letter_template": "Dear {company} team, I am excited about {job_title}.",
        },
        headers=headers,
    )


def test_generate_resume_queues(client: TestClient) -> None:
    headers = register_and_login(client, "docgen-resume@example.com")
    job_id = _seed_job(client, headers)
    _put_profile(client, headers)

    with patch.object(generate_resume_task, "delay") as mock_delay:
        resp = client.post(f"/api/v1/jobs/{job_id}/generate-resume", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["kind"] == "resume"
    assert body["result"] is None
    generation_id = body["id"]
    mock_delay.assert_called_once_with(generation_id, mock_delay.call_args[0][1], job_id)

    polled = client.get(f"/api/v1/document-generations/{generation_id}", headers=headers)
    assert polled.status_code == 200
    assert polled.json()["status"] == "queued"


def test_generate_cover_letter_queues(client: TestClient) -> None:
    headers = register_and_login(client, "docgen-cover@example.com")
    job_id = _seed_job(client, headers)
    _put_profile(client, headers)

    with patch.object(generate_cover_letter_task, "delay") as mock_delay:
        resp = client.post(f"/api/v1/jobs/{job_id}/generate-cover-letter", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["kind"] == "cover_letter"
    mock_delay.assert_called_once()
    generation_id = body["id"]
    assert (
        client.get(f"/api/v1/document-generations/{generation_id}", headers=headers).json()[
            "status"
        ]
        == "queued"
    )


def test_document_generation_get_scopes_by_user(client: TestClient) -> None:
    alice = register_and_login(client, "docgen-alice@example.com")
    job_id = _seed_job(client, alice)
    _put_profile(client, alice)
    with patch.object(generate_resume_task, "delay"):
        generation_id = client.post(f"/api/v1/jobs/{job_id}/generate-resume", headers=alice).json()[
            "id"
        ]

    bob = register_and_login(client, "docgen-bob@example.com")
    resp = client.get(f"/api/v1/document-generations/{generation_id}", headers=bob)
    assert resp.status_code == 404


def test_generate_resume_requires_profile(client: TestClient) -> None:
    headers = register_and_login(client, "docgen-no-profile@example.com")
    job_id = _seed_job(client, headers)
    resp = client.post(f"/api/v1/jobs/{job_id}/generate-resume", headers=headers)
    assert resp.status_code == 400
    assert "application profile" in resp.json()["detail"].lower()


def test_generate_cover_letter_requires_profile(client: TestClient) -> None:
    headers = register_and_login(client, "docgen-cover-noprofile@example.com")
    job_id = _seed_job(client, headers)
    resp = client.post(f"/api/v1/jobs/{job_id}/generate-cover-letter", headers=headers)
    assert resp.status_code == 400
    assert "application profile" in resp.json()["detail"].lower()


def test_generate_resume_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/jobs/1/generate-resume").status_code == 401


def test_generate_cover_letter_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/jobs/1/generate-cover-letter").status_code == 401


def test_document_generation_get_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/document-generations/1").status_code == 401
