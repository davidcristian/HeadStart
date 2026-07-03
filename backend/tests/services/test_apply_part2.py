"""Tests for apply orchestration service (pipeline, existing-log, and validation)."""

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


def _enable_and_profile(db_session: Session, job: SeenJob, user_id: int) -> None:
    source = db_session.get(Source, job.search.source_id)
    assert source is not None
    source.auto_apply_enabled = True
    db_session.flush()
    ProfileService(db_session).save(
        user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )


def test_enqueue_auto_apply_from_pipeline_queues_when_eligible(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)

    queued = ApplyService(db_session).enqueue_auto_apply_from_pipeline(user_id, job_id)

    assert queued is not None
    assert queued.job_id == job_id
    assert queued.user_id == user_id
    log = db_session.get(ApplicationLog, queued.application_log_id)
    assert log is not None
    assert log.status == "queued"


def test_enqueue_auto_apply_from_pipeline_skips_when_source_missing(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)
    # Repoint the search at a source id that no longer resolves for this user.
    job.search.source_id = 987654
    db_session.flush()

    assert ApplyService(db_session).enqueue_auto_apply_from_pipeline(user_id, job_id) is None


def test_enqueue_auto_apply_ineligible_when_adapter_unsupported(db_session: Session) -> None:
    search = _make_search(db_session)
    source = db_session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "rss"  # no applier registered
    source.auto_apply_enabled = True
    db_session.flush()
    job = SeenJob(
        search_id=search.id,
        external_id="rss-2",
        hash="rss-2",
        title="Engineer",
        company="ACME",
        url="https://example.test/rss/2",
        status="new",
    )
    db_session.add(job)
    db_session.flush()
    ProfileService(db_session).save(
        search.user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com"),
    )

    assert ApplyService(db_session).enqueue_auto_apply_from_pipeline(search.user_id, job.id) is None


def test_enqueue_auto_apply_from_pipeline_skips_when_not_opted_in(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    ProfileService(db_session).save(
        user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )
    # auto_apply_enabled stays False -> ineligible.
    assert ApplyService(db_session).enqueue_auto_apply_from_pipeline(user_id, job_id) is None
    assert db_session.query(ApplicationLog).count() == 0


def test_enqueue_auto_apply_from_pipeline_skips_when_pending_exists(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)
    first = ApplyService(db_session).enqueue_auto_apply_from_pipeline(user_id, job_id)
    assert first is not None

    assert ApplyService(db_session).enqueue_auto_apply_from_pipeline(user_id, job_id) is None
    assert db_session.query(ApplicationLog).count() == 1


def test_enqueue_auto_apply_ineligible_when_no_profile(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    source = db_session.get(Source, job.search.source_id)
    assert source is not None
    source.auto_apply_enabled = True
    db_session.flush()
    # No profile saved -> _pipeline_auto_apply_eligible returns False on profile check.
    assert ApplyService(db_session).enqueue_auto_apply_from_pipeline(user_id, job_id) is None


def test_apply_with_existing_queued_log_updates_it(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)
    log_id = ApplyService(db_session).enqueue_apply(user_id, job_id)

    with patch("app.services.apply.get_applier") as mock_get_applier:
        mock_get_applier.return_value.apply.return_value = ApplyResult(
            status="submitted",
            payload={"email": "ada@example.com"},
            external_application_id="app-9",
        )
        result = ApplyService(db_session).apply_to_job(
            user_id, job_id, dry_run=False, application_log_id=log_id
        )

    assert result.status == "submitted"
    log = db_session.get(ApplicationLog, log_id)
    assert log is not None
    assert log.status == "submitted"
    assert log.external_application_id == "app-9"
    # No extra audit row is created; the queued log is updated in place.
    assert db_session.query(ApplicationLog).count() == 1


def test_apply_with_existing_log_rejects_non_queued(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)
    log_id = ApplyService(db_session).enqueue_apply(user_id, job_id)
    log = db_session.get(ApplicationLog, log_id)
    assert log is not None
    log.status = "submitted"
    db_session.flush()

    try:
        ApplyService(db_session).apply_to_job(
            user_id, job_id, dry_run=False, application_log_id=log_id
        )
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "no longer queued" in str(exc).lower()


def test_apply_with_unknown_log_id_raises(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)

    try:
        ApplyService(db_session).apply_to_job(
            user_id, job_id, dry_run=False, application_log_id=999999
        )
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass


def test_apply_records_tailored_resume_in_payload(db_session: Session) -> None:
    import base64

    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)
    resume_b64 = base64.b64encode(b"%PDF-1.4\ntailored\n").decode("ascii")

    with patch("app.services.apply.get_applier") as mock_get_applier:
        mock_get_applier.return_value.apply.return_value = ApplyResult(
            status="submitted",
            payload=None,
        )
        result = ApplyService(db_session).apply_to_job(
            user_id, job_id, dry_run=False, tailored_resume_b64=resume_b64
        )

    assert result.status == "submitted"
    logs = db_session.query(ApplicationLog).all()
    assert len(logs) == 1
    assert logs[0].payload["tailored_resume"]["content_type"] == "application/pdf"
    assert logs[0].tailored_resume_artifact_id is not None


def test_fail_queued_apply_marks_failed(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)
    log_id = ApplyService(db_session).enqueue_apply(user_id, job_id)

    ApplyService(db_session).fail_queued_apply(log_id, "worker crashed")

    log = db_session.get(ApplicationLog, log_id)
    assert log is not None
    assert log.status == "failed"
    assert log.error == "worker crashed"


def test_fail_queued_apply_ignores_missing_or_terminal(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    _enable_and_profile(db_session, job, user_id)
    log_id = ApplyService(db_session).enqueue_apply(user_id, job_id)
    log = db_session.get(ApplicationLog, log_id)
    assert log is not None
    log.status = "submitted"
    db_session.flush()

    # Unknown id -> no-op.
    ApplyService(db_session).fail_queued_apply(999999, "x")
    # Terminal status -> no-op.
    ApplyService(db_session).fail_queued_apply(log_id, "x")

    db_session.refresh(log)
    assert log.status == "submitted"


def test_validate_apply_request_source_not_found(db_session: Session) -> None:
    user_id, job_id, job = _seed_greenhouse_job(db_session)
    ProfileService(db_session).save(
        user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )
    # Point the job's search at a source id that does not exist for this user.
    job.search.source_id = 987654
    db_session.flush()

    try:
        ApplyService(db_session).apply_to_job(user_id, job_id, dry_run=True)
        raise AssertionError("expected NotFoundError")
    except NotFoundError as exc:
        assert "Source" in str(exc)


def test_validate_apply_request_unsupported_adapter(db_session: Session) -> None:
    search = _make_search(db_session)
    source = db_session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "rss"  # no applier registered
    db_session.flush()
    job = SeenJob(
        search_id=search.id,
        external_id="rss-1",
        hash="rss-1",
        title="Engineer",
        company="ACME",
        url="https://example.test/rss/1",
        status="new",
    )
    db_session.add(job)
    db_session.flush()
    ProfileService(db_session).save(
        search.user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com"),
    )

    try:
        ApplyService(db_session).apply_to_job(search.user_id, job.id, dry_run=True)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "does not support auto-apply" in str(exc)
