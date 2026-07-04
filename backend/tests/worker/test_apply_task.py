"""Worker tests for queued auto-apply."""

from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy.orm import Session, sessionmaker

from app.appliers.types import ApplyResult
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.schemas.profile import ProfileData
from app.services.apply import ApplyService
from app.services.profiles import ProfileService
from app.worker.tasks import apply_to_job_task
from tests.worker.test_pipeline import _make_search


def _session_factory_for(session: Session) -> sessionmaker[Session]:
    return sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


def _seed_greenhouse_job(session: Session) -> tuple[int, int, int]:
    search = _make_search(session)
    source = session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "greenhouse"
    source.auto_apply_enabled = True
    source.default_config = {"board_token": "acme", "job_board_api_key": "test-key"}
    session.flush()

    job = SeenJob(
        search_id=search.id,
        external_id="5501001",
        hash="gh-worker-1",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
        url="https://boards.greenhouse.io/acme/jobs/5501001",
        status="new",
    )
    session.add(job)
    session.flush()
    ProfileService(session).save(
        search.user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )
    log_id = ApplyService(session).enqueue_apply(search.user_id, job.id)
    session.commit()
    return search.user_id, job.id, log_id


def test_apply_to_job_task_completes_queued_apply(db_session: Session) -> None:
    user_id, job_id, log_id = _seed_greenhouse_job(db_session)

    @contextmanager
    def test_scope():
        yield db_session
        db_session.commit()

    with (
        patch("app.worker.tasks.session_scope", test_scope),
        patch("app.services.apply.get_applier") as mock_get_applier,
    ):
        mock_get_applier.return_value.apply.return_value = ApplyResult(
            status="submitted",
            payload={"email": "ada@example.com"},
            external_application_id="app-worker-1",
        )
        result = apply_to_job_task(log_id, user_id, job_id, "Hello")

    assert result["status"] == "submitted"
    log = db_session.get(ApplicationLog, log_id)
    assert log is not None
    assert log.status == "submitted"
    assert log.external_application_id == "app-worker-1"
    job = db_session.get(SeenJob, job_id)
    assert job is not None
    assert job.status == "applied"
    assert job.applied_at is not None


def test_apply_to_job_task_skips_when_not_queued(db_session: Session) -> None:
    """Redelivery after a durable processing claim must not call the applier."""
    user_id, job_id, log_id = _seed_greenhouse_job(db_session)
    log = db_session.get(ApplicationLog, log_id)
    assert log is not None
    log.status = "processing"
    db_session.commit()

    @contextmanager
    def test_scope():
        yield db_session
        db_session.commit()

    with (
        patch("app.worker.tasks.session_scope", test_scope),
        patch("app.services.apply.get_applier") as mock_get_applier,
    ):
        result = apply_to_job_task(log_id, user_id, job_id, None)

    assert result["status"] == "skipped"
    assert result["error"] == "not_queued"
    mock_get_applier.assert_not_called()
    db_session.refresh(log)
    assert log.status == "processing"


def test_apply_to_job_task_leaves_processing_on_exception(db_session: Session) -> None:
    """Uncertain post-claim failures must not reopen the in-flight unique index."""
    user_id, job_id, log_id = _seed_greenhouse_job(db_session)
    factory = _session_factory_for(db_session)

    with (
        patch("app.core.db.SessionFactory", factory),
        patch.object(ApplyService, "apply_to_job", side_effect=RuntimeError("boom")),
    ):
        result = apply_to_job_task(log_id, user_id, job_id, None)

    assert result["status"] == "failed"
    assert result["error"] == "boom"
    db_session.expire_all()
    log = db_session.get(ApplicationLog, log_id)
    assert log is not None
    assert log.status == "processing"
