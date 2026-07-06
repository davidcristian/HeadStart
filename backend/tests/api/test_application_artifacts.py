"""API tests for application artifact download."""

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.appliers import ApplyResult
from app.main import app
from app.scrapers.types import JobPosting
from app.services.document_generations import DocumentGenerationService
from app.services.pipeline import PipelineService
from app.services.resumes import ResumeService
from app.worker.tasks import generate_resume_task
from tests.conftest import register_and_login

FAKE_PDF = b"%PDF-1.4\nfake resume\n"


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
        client.post(f"/api/v1/searches/{search_id}/run", headers=headers)
    return client.get("/api/v1/jobs", headers=headers).json()[0]["id"]


@contextmanager
def _client_db_session() -> Iterator[Session]:
    """Open a session from the TestClient's get_db override (same in-memory DB)."""
    db_gen = app.dependency_overrides[get_db]()
    session = next(db_gen)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        with suppress(StopIteration):
            next(db_gen)


def _complete_queued_resume(generation_id: int, user_id: int, job_id: int) -> None:
    """Run claim + compile for a queued generate-resume without Celery/Redis."""
    with _client_db_session() as session:
        service = DocumentGenerationService(session)
        assert service.claim(generation_id) is not None
    with (
        _client_db_session() as session,
        patch.object(ResumeService, "_compile_pdf", return_value=FAKE_PDF),
    ):
        DocumentGenerationService(session).complete_resume(generation_id, user_id, job_id)


def test_generate_resume_persists_artifact(client: TestClient) -> None:
    headers = register_and_login(client, "artifact-generate@example.com")
    job_id = _seed_job(client, headers)
    client.put(
        "/api/v1/profile",
        json={"full_name": "Ada Lovelace", "email": "ada@example.com"},
        headers=headers,
    )

    with patch.object(generate_resume_task, "delay") as mock_delay:
        resp = client.post(f"/api/v1/jobs/{job_id}/generate-resume", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    generation_id = body["id"]
    user_id = mock_delay.call_args[0][1]
    _complete_queued_resume(generation_id, user_id, job_id)

    ready = client.get(f"/api/v1/document-generations/{generation_id}", headers=headers).json()
    assert ready["status"] == "ready"
    artifact_id = ready["result"]["artifact_id"]
    assert artifact_id > 0

    meta = client.get(f"/api/v1/application-artifacts/{artifact_id}", headers=headers)
    assert meta.status_code == 200
    assert meta.json()["filename"] == ready["result"]["filename"]

    download = client.get(
        f"/api/v1/application-artifacts/{artifact_id}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == FAKE_PDF
    assert download.headers["content-type"] == "application/pdf"


def test_apply_with_artifact_id_links_log(client: TestClient) -> None:
    headers = register_and_login(client, "artifact-apply@example.com")
    job_id = _seed_job(client, headers)
    client.put(
        "/api/v1/profile",
        json={"full_name": "Ada Lovelace", "email": "ada@example.com"},
        headers=headers,
    )
    client.patch(
        f"/api/v1/sources/{client.get('/api/v1/sources', headers=headers).json()[0]['id']}",
        json={"auto_apply_enabled": True},
        headers=headers,
    )

    with patch.object(generate_resume_task, "delay") as mock_delay:
        queued = client.post(
            f"/api/v1/jobs/{job_id}/generate-resume",
            headers=headers,
        ).json()
    _complete_queued_resume(queued["id"], mock_delay.call_args[0][1], job_id)
    artifact_id = client.get(
        f"/api/v1/document-generations/{queued['id']}", headers=headers
    ).json()["result"]["artifact_id"]

    with patch("app.appliers.adapters.greenhouse.GreenhouseApplier.apply") as mock_apply:
        mock_apply.return_value = ApplyResult(status="dry_run", payload={"ok": True})
        resp = client.post(
            f"/api/v1/jobs/{job_id}/apply",
            json={"dry_run": True, "tailored_resume_artifact_id": artifact_id},
            headers=headers,
        )

    assert resp.status_code == 200
    logs = client.get("/api/v1/application-logs", headers=headers).json()
    assert logs[0]["tailored_resume_artifact"]["id"] == artifact_id


def test_artifact_download_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/application-artifacts/1/download").status_code == 401
