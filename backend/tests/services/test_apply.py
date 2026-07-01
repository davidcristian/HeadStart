"""Tests for apply orchestration service."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.appliers.types import ApplyResult
from app.core.exceptions import NotFoundError, ValidationError
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.schemas.profile import ProfileData
from app.services.apply import ApplyService
from app.services.profiles import ProfileService
from tests.worker.test_pipeline import _make_search


def _seed_greenhouse_job(session: Session) -> tuple[int, int, SeenJob]:
    search = _make_search(session)
    source = session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "greenhouse"
    source.default_config = {"board_token": "acme", "job_board_api_key": "test-key"}
    session.flush()

    job = SeenJob(
        search_id=search.id,
        external_id="5501001",
        hash="gh-1",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/5501001",
        status="new",
    )
    session.add(job)
    session.flush()
    return search.user_id, job.id, job


def test_apply_service_dry_run_without_profile_fails(db_session: Session) -> None:
    user_id, job_id, _ = _seed_greenhouse_job(db_session)
    try:
        ApplyService(db_session).apply_to_job(user_id, job_id, dry_run=True)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "profile" in str(exc).lower()


def test_apply_service_dry_run_returns_payload(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    ProfileService(db_session).save(
        user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )

    result = ApplyService(db_session).apply_to_job(user_id, job_id, dry_run=True)

    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["email"] == "ada@example.com"
    db_session.refresh(job)
    assert job.status == "new"
    logs = db_session.query(ApplicationLog).all()
    assert len(logs) == 1
    assert logs[0].status == "dry_run"
    assert logs[0].dry_run is True
    assert logs[0].payload is not None


def test_apply_service_live_without_opt_in_fails(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    ProfileService(db_session).save(
        user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )

    try:
        ApplyService(db_session).apply_to_job(user_id, job_id, dry_run=False)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "auto-apply" in str(exc).lower()

    db_session.refresh(job)
    assert job.status == "new"
    assert db_session.query(ApplicationLog).count() == 0


def test_apply_service_live_with_opt_in_records_log(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    source = db_session.get(Source, job.search.source_id)
    assert source is not None
    source.auto_apply_enabled = True
    db_session.flush()
    ProfileService(db_session).save(
        user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )

    with patch("app.services.apply.get_applier") as mock_get_applier:
        mock_get_applier.return_value.apply.return_value = ApplyResult(
            status="submitted",
            payload={"email": "ada@example.com"},
            external_application_id="app-1",
        )
        result = ApplyService(db_session).apply_to_job(user_id, job_id, dry_run=False)

    assert result.status == "submitted"
    db_session.refresh(job)
    assert job.status == "applied"
    logs = db_session.query(ApplicationLog).all()
    assert len(logs) == 1
    assert logs[0].status == "submitted"
    assert logs[0].dry_run is False
    assert logs[0].external_application_id == "app-1"


def test_apply_service_rejects_unsupported_adapter(db_session: Session) -> None:
    search = _make_search(db_session)
    source = db_session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "workday"
    db_session.flush()
    job = SeenJob(
        search_id=search.id,
        external_id="1",
        hash="x",
        title="Role",
        company="Co",
        url="https://jobs.lever.co/acme/1",
        status="new",
    )
    db_session.add(job)
    db_session.flush()
    ProfileService(db_session).save(
        search.user_id, ProfileData(full_name="Ada Lovelace", email="ada@example.com")
    )

    try:
        ApplyService(db_session).apply_to_job(search.user_id, job.id, dry_run=True)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "workday" in str(exc)


def test_apply_service_scopes_jobs_by_user(db_session: Session) -> None:
    user_id, job_id, _ = _seed_greenhouse_job(db_session)
    other = _make_search(db_session)
    ProfileService(db_session).save(
        user_id, ProfileData(full_name="Ada Lovelace", email="ada@example.com")
    )

    try:
        ApplyService(db_session).apply_to_job(other.user_id, job_id, dry_run=True)
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass
