"""Pipeline integration tests for automatic apply queueing."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.application_log import ApplicationLog
from app.models.source import Source
from app.models.user import User
from app.schemas.profile import ProfileData
from app.services.profiles import ProfileService
from app.worker.tasks import run_search
from tests.worker.pipeline_helpers import (
    FakeScraper,
    RecordingNotifier,
    make_search,
    pipeline,
    posting,
)


def _enable_greenhouse_auto_apply(session: Session, search) -> None:
    source = session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "greenhouse"
    source.auto_apply_enabled = True
    source.default_config = {"board_token": "acme", "job_board_api_key": "test-key"}
    session.flush()


def _save_profile(session: Session, user_id: int) -> None:
    ProfileService(session).save(
        user_id,
        ProfileData(full_name="Ada Lovelace", email="ada@example.com", resume_text="CV"),
    )


def test_pipeline_queues_auto_apply_for_new_jobs(db_session: Session) -> None:
    search = make_search(db_session)
    _enable_greenhouse_auto_apply(db_session, search)
    _save_profile(db_session, search.user_id)

    result = pipeline(
        db_session,
        FakeScraper([posting("1")]),
        RecordingNotifier(),
    ).run(search.id)

    assert result.auto_apply_queued == 1
    assert len(result.pending_auto_applies) == 1
    queued = result.pending_auto_applies[0]
    assert queued.user_id == search.user_id
    log = db_session.get(ApplicationLog, queued.application_log_id)
    assert log is not None
    assert log.status == "queued"
    assert log.payload is not None
    assert log.payload["employer_domain"] == "acme.test"
    assert log.payload["posting"]["title"] == "Job 1"


def test_pipeline_skips_auto_apply_without_opt_in(db_session: Session) -> None:
    search = make_search(db_session)
    _save_profile(db_session, search.user_id)

    result = pipeline(
        db_session,
        FakeScraper([posting("1")]),
        RecordingNotifier(),
    ).run(search.id)

    assert result.auto_apply_queued == 0
    assert db_session.query(ApplicationLog).count() == 0


def test_pipeline_skips_auto_apply_without_profile(db_session: Session) -> None:
    search = make_search(db_session)
    _enable_greenhouse_auto_apply(db_session, search)

    result = pipeline(
        db_session,
        FakeScraper([posting("1")]),
        RecordingNotifier(),
    ).run(search.id)

    assert result.auto_apply_queued == 0
    assert db_session.query(ApplicationLog).count() == 0


def test_pipeline_skips_auto_apply_for_unsupported_adapter(db_session: Session) -> None:
    search = make_search(db_session)
    source = db_session.get(Source, search.source_id)
    assert source is not None
    source.adapter_key = "generic_html"
    source.auto_apply_enabled = True
    db_session.flush()
    _save_profile(db_session, search.user_id)

    result = pipeline(
        db_session,
        FakeScraper([posting("1")]),
        RecordingNotifier(),
    ).run(search.id)

    assert result.auto_apply_queued == 0


def test_pipeline_auto_apply_runs_for_cross_search_skipped_notifications(
    db_session: Session,
) -> None:
    """Auto-apply still queues when notification is skipped by cross-search dedup."""
    first = make_search(db_session)
    _enable_greenhouse_auto_apply(db_session, first)
    _save_profile(db_session, first.user_id)
    shared_url = "https://acme.test/shared"

    pipeline(
        db_session,
        FakeScraper([posting("1", url=shared_url)]),
        RecordingNotifier(),
    ).run(first.id)

    second = make_search(db_session, user=db_session.get(User, first.user_id))
    source = db_session.get(Source, second.source_id)
    assert source is not None
    source.adapter_key = "greenhouse"
    source.auto_apply_enabled = True
    source.default_config = {"board_token": "acme", "job_board_api_key": "test-key"}
    db_session.flush()

    notifier = RecordingNotifier()
    result = pipeline(
        db_session,
        FakeScraper([posting("2", url=shared_url)]),
        notifier,
    ).run(second.id)

    assert result.new == 1
    assert result.skipped == 1
    assert result.notified == 0
    assert result.auto_apply_queued == 1


def test_run_search_dispatches_auto_apply_after_commit() -> None:
    from app.services.apply import QueuedAutoApply
    from app.services.pipeline import RunResult

    queued = QueuedAutoApply(application_log_id=10, user_id=20, job_id=30, cover_letter=None)
    mock_result = RunResult(search_id=1, pending_auto_applies=[queued])

    with (
        patch("app.worker.tasks.PipelineService") as mock_cls,
        patch("app.worker.tasks.apply_to_job_task.delay") as mock_delay,
        patch("app.worker.tasks.session_scope") as mock_scope,
    ):
        mock_scope.return_value.__enter__.return_value = object()
        mock_scope.return_value.__exit__.return_value = None
        mock_cls.return_value.run.return_value = mock_result

        run_search(1)

    mock_delay.assert_called_once_with(10, 20, 30, None)
