"""Tests for job lifecycle (status updates and closed detection)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.seen_job import SeenJob
from app.schemas.job import JobUpdate
from app.services.jobs import JobService
from app.services.pipeline import PipelineService
from tests.conftest import register_and_login
from tests.worker.test_pipeline import (
    FakeScraper,
    RecordingNotifier,
    _make_search,
    _pipeline,
    _posting,
)


def _seed_job(db_session: Session, search_id: int, external_id: str = "job-1") -> SeenJob:
    job = SeenJob(
        search_id=search_id,
        external_id=external_id,
        hash="abc",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://acme.test/jobs/1",
        status="new",
    )
    db_session.add(job)
    db_session.flush()
    return job


def test_job_service_updates_status(db_session: Session) -> None:
    search = _make_search(db_session)
    job = _seed_job(db_session, search.id)

    updated = JobService(db_session).update(job.id, search.user_id, JobUpdate(status="applied"))

    assert updated.status == "applied"


def test_job_service_scopes_by_user(db_session: Session) -> None:
    search = _make_search(db_session)
    job = _seed_job(db_session, search.id)
    other = _make_search(db_session)

    try:
        JobService(db_session).update(job.id, other.user_id, JobUpdate(status="seen"))
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass


def test_job_service_filters_by_status(db_session: Session) -> None:
    search = _make_search(db_session)
    new_job = _seed_job(db_session, search.id, external_id="new")
    applied = _seed_job(db_session, search.id, external_id="applied")
    applied.status = "applied"
    db_session.flush()

    jobs = JobService(db_session).list_all(user_id=search.user_id, status="applied")

    assert [j.id for j in jobs] == [applied.id]
    assert new_job.id not in {j.id for j in jobs}


def test_pipeline_marks_missing_jobs_closed(db_session: Session) -> None:
    search = _make_search(db_session)
    job = _seed_job(db_session, search.id, external_id="gone")

    result = _pipeline(db_session, FakeScraper([_posting("still-here")]), RecordingNotifier()).run(
        search.id
    )

    assert result.closed == 1
    db_session.refresh(job)
    assert job.status == "closed"


def test_pipeline_does_not_close_applied_or_archived_jobs(db_session: Session) -> None:
    search = _make_search(db_session)
    applied = _seed_job(db_session, search.id, external_id="applied")
    applied.status = "applied"
    archived = _seed_job(db_session, search.id, external_id="archived")
    archived.status = "archived"
    db_session.flush()

    result = _pipeline(db_session, FakeScraper([]), RecordingNotifier()).run(search.id)

    assert result.closed == 0
    db_session.refresh(applied)
    db_session.refresh(archived)
    assert applied.status == "applied"
    assert archived.status == "archived"


def test_pipeline_reopens_closed_job_when_it_reappears(db_session: Session) -> None:
    search = _make_search(db_session)
    job = _seed_job(db_session, search.id, external_id="back")
    job.status = "closed"
    db_session.flush()

    _pipeline(db_session, FakeScraper([_posting("back")]), RecordingNotifier()).run(search.id)

    db_session.refresh(job)
    assert job.status == "seen"


def test_job_api_patch_and_filter(client: TestClient, auth_headers: dict[str, str]) -> None:
    from unittest.mock import patch

    from app.scrapers.types import JobPosting

    source_id = client.post(
        "/api/v1/sources",
        json={"name": "ACME", "adapter_key": "greenhouse"},
        headers=auth_headers,
    ).json()["id"]
    target_id = client.post(
        "/api/v1/targets",
        json={"name": "Phone", "type": "ntfy", "config": {"topic": "abc"}},
        headers=auth_headers,
    ).json()["id"]
    search_id = client.post(
        "/api/v1/searches",
        json={
            "name": "ACME SWE",
            "source_id": source_id,
            "target_id": target_id,
            "interval_seconds": 60,
        },
        headers=auth_headers,
    ).json()["id"]

    posting = JobPosting(
        external_id="api-job",
        title="Engineer",
        company="ACME",
        location="Remote",
        url="https://acme.test/api-job",
    )
    with patch.object(PipelineService, "scrape", return_value=[posting]):
        client.post(f"/api/v1/searches/{search_id}/run", headers=auth_headers)

    jobs = client.get("/api/v1/jobs", headers=auth_headers).json()
    assert len(jobs) == 1
    job_id = jobs[0]["id"]
    assert jobs[0]["status"] == "new"

    patched = client.patch(
        f"/api/v1/jobs/{job_id}", json={"status": "applied"}, headers=auth_headers
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "applied"

    filtered = client.get("/api/v1/jobs?status=applied", headers=auth_headers).json()
    assert len(filtered) == 1
    assert filtered[0]["id"] == job_id

    bob = register_and_login(client, "bob-jobs@example.com")
    assert (
        client.patch(f"/api/v1/jobs/{job_id}", json={"status": "seen"}, headers=bob).status_code
        == 404
    )


def test_users_cannot_see_each_others_jobs(client: TestClient) -> None:
    from unittest.mock import patch

    from app.scrapers.types import JobPosting

    alice = register_and_login(client, "alice-jobs@example.com")
    bob = register_and_login(client, "bob-jobs2@example.com")

    source_id = client.post(
        "/api/v1/sources",
        json={"name": "ACME", "adapter_key": "greenhouse"},
        headers=alice,
    ).json()["id"]
    search_id = client.post(
        "/api/v1/searches",
        json={"name": "SWE", "source_id": source_id, "interval_seconds": 60},
        headers=alice,
    ).json()["id"]

    with patch.object(
        PipelineService,
        "scrape",
        return_value=[
            JobPosting(
                external_id="x",
                title="Role",
                company="ACME",
                location="",
                url="https://acme.test/x",
            )
        ],
    ):
        client.post(f"/api/v1/searches/{search_id}/run", headers=alice)

    assert client.get("/api/v1/jobs", headers=bob).json() == []
