"""Route tests for job auto-apply."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.worker.tasks import apply_to_job_task
from tests.conftest import post_search_run, register_and_login


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
        post_search_run(client, search_id, headers)
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


def test_apply_live_queues_and_returns_log_id(client: TestClient) -> None:
    headers = register_and_login(client, "apply-live@example.com")
    job_id = _seed_greenhouse_job_via_api(client, headers)
    source_id = client.get("/api/v1/sources", headers=headers).json()[0]["id"]
    client.patch(
        f"/api/v1/sources/{source_id}",
        json={"auto_apply_enabled": True},
        headers=headers,
    )
    client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "resume_text": "CV",
        },
        headers=headers,
    )

    with patch.object(apply_to_job_task, "delay") as mock_delay:
        resp = client.post(
            f"/api/v1/jobs/{job_id}/apply",
            json={"dry_run": False, "cover_letter": "Hello"},
            headers=headers,
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["application_log_id"] is not None
    assert body["job"] is None
    mock_delay.assert_called_once()
    delay_args = mock_delay.call_args[0]
    log_id = delay_args[0]
    queued_job_id = delay_args[2]
    cover_letter = delay_args[3]
    tailored_resume_b64 = delay_args[4]
    tailored_resume_artifact_id = delay_args[5]
    assert log_id == body["application_log_id"]
    assert queued_job_id == job_id
    assert cover_letter == "Hello"
    assert tailored_resume_b64 is None
    assert tailored_resume_artifact_id is None

    log_resp = client.get(
        f"/api/v1/application-logs/{body['application_log_id']}",
        headers=headers,
    )
    assert log_resp.status_code == 200
    assert log_resp.json()["status"] == "queued"


def test_apply_live_commits_before_worker_enqueue(client: TestClient) -> None:
    headers = register_and_login(client, "apply-commit-order@example.com")
    job_id = _seed_greenhouse_job_via_api(client, headers)
    source_id = client.get("/api/v1/sources", headers=headers).json()[0]["id"]
    client.patch(
        f"/api/v1/sources/{source_id}",
        json={"auto_apply_enabled": True},
        headers=headers,
    )
    client.put(
        "/api/v1/profile",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "resume_text": "CV",
        },
        headers=headers,
    )

    events: list[str] = []
    original_commit = Session.commit

    def tracking_commit(self: Session) -> None:
        events.append("commit")
        original_commit(self)

    def tracking_delay(*_args: object, **_kwargs: object) -> None:
        events.append("delay")

    with (
        patch.object(Session, "commit", tracking_commit),
        patch.object(apply_to_job_task, "delay", tracking_delay),
    ):
        resp = client.post(
            f"/api/v1/jobs/{job_id}/apply",
            json={"dry_run": False},
            headers=headers,
        )

    assert resp.status_code == 202
    assert "delay" in events
    assert events.index("delay") > events.index("commit")


def test_get_application_log_scopes_by_user(client: TestClient) -> None:
    alice = register_and_login(client, "apply-log-alice@example.com")
    job_id = _seed_greenhouse_job_via_api(client, alice)
    source_id = client.get("/api/v1/sources", headers=alice).json()[0]["id"]
    client.patch(f"/api/v1/sources/{source_id}", json={"auto_apply_enabled": True}, headers=alice)
    client.put(
        "/api/v1/profile",
        json={"full_name": "Ada Lovelace", "email": "ada@example.com"},
        headers=alice,
    )

    with patch.object(apply_to_job_task, "delay"):
        queued = client.post(
            f"/api/v1/jobs/{job_id}/apply",
            json={"dry_run": False},
            headers=alice,
        )
    log_id = queued.json()["application_log_id"]

    bob = register_and_login(client, "apply-log-bob@example.com")
    assert client.get(f"/api/v1/application-logs/{log_id}", headers=bob).status_code == 404


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
