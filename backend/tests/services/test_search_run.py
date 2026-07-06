"""Tests for async manual search runs (API-02)."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.base import utcnow
from app.models.search_run import SearchRun
from app.services.pipeline import PipelineService, RunResult
from app.services.search_runs import SearchRunService
from app.worker.tasks import run_search_run_task
from tests.worker.test_pipeline import _make_search


def test_enqueue_and_complete_returns_counts(db_session: Session) -> None:
    search = _make_search(db_session)
    service = SearchRunService(db_session)
    queued = service.enqueue(search.user_id, search.id)
    assert queued.status == "queued"
    assert queued.search_id == search.id

    claimed = service.claim(queued.id)
    assert claimed is not None
    assert claimed.status == "processing"

    expected = RunResult(search_id=search.id, found=2, new=1, notified=1, failed=0, error=None)
    with patch.object(PipelineService, "run", return_value=expected):
        pending = service.complete(queued.id, search.user_id, search.id)
    assert pending == []

    done = service.get_for_user(search.user_id, queued.id)
    assert done.status == "ready"
    assert done.found == 2
    assert done.new == 1
    assert done.notified == 1
    assert done.error is None


def test_complete_marks_failed_on_pipeline_error(db_session: Session) -> None:
    search = _make_search(db_session)
    service = SearchRunService(db_session)
    queued = service.enqueue(search.user_id, search.id)
    service.claim(queued.id)
    expected = RunResult(search_id=search.id, error="scrape boom")
    with patch.object(PipelineService, "run", return_value=expected):
        service.complete(queued.id, search.user_id, search.id)
    done = service.get_for_user(search.user_id, queued.id)
    assert done.status == "failed"
    assert done.error == "scrape boom"


def test_claim_skips_non_queued(db_session: Session) -> None:
    search = _make_search(db_session)
    row = SearchRun(
        user_id=search.user_id,
        search_id=search.id,
        status="ready",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.commit()
    assert SearchRunService(db_session).claim(row.id) is None


def test_get_for_user_missing(db_session: Session) -> None:
    search = _make_search(db_session)
    try:
        SearchRunService(db_session).get_for_user(search.user_id, 999999)
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass


def test_enqueue_missing_search(db_session: Session) -> None:
    try:
        SearchRunService(db_session).enqueue(1, 999999)
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass


def test_complete_skips_when_not_processing(db_session: Session) -> None:
    search = _make_search(db_session)
    service = SearchRunService(db_session)
    queued = service.enqueue(search.user_id, search.id)
    assert service.complete(queued.id, search.user_id, search.id) == []


def test_complete_rejects_mismatched_search(db_session: Session) -> None:
    search = _make_search(db_session)
    service = SearchRunService(db_session)
    queued = service.enqueue(search.user_id, search.id)
    service.claim(queued.id)
    try:
        service.complete(queued.id, search.user_id, search.id + 1)
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass


def test_claim_missing_row(db_session: Session) -> None:
    assert SearchRunService(db_session).claim(999999) is None


def test_from_row_with_non_dict_result(db_session: Session) -> None:
    search = _make_search(db_session)
    row = SearchRun(
        user_id=search.user_id,
        search_id=search.id,
        status="ready",
        result=None,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.flush()
    from app.schemas.search_run import SearchRunRead

    read = SearchRunRead.from_row(row)
    assert read.found == 0
    assert read.status == "ready"


def test_complete_missing_row(db_session: Session) -> None:
    try:
        SearchRunService(db_session).complete(999999, 1, 1)
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass


def test_run_search_run_task_skips_when_not_queued(db_session: Session) -> None:
    search = _make_search(db_session)
    row = SearchRun(
        user_id=search.user_id,
        search_id=search.id,
        status="processing",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(row)
    db_session.commit()

    from contextlib import contextmanager

    @contextmanager
    def test_scope():
        yield db_session
        db_session.commit()

    with patch("app.worker.tasks.session_scope", test_scope):
        result = run_search_run_task(row.id, search.user_id, search.id)
    assert result["status"] == "skipped"


def test_run_search_run_task_dispatches_auto_applies(db_session: Session) -> None:
    from app.services.apply import QueuedAutoApply

    search = _make_search(db_session)
    service = SearchRunService(db_session)
    queued = service.enqueue(search.user_id, search.id)
    db_session.commit()

    from contextlib import contextmanager

    @contextmanager
    def test_scope():
        yield db_session
        db_session.commit()

    pending = [
        QueuedAutoApply(
            application_log_id=11,
            user_id=search.user_id,
            job_id=22,
            cover_letter=None,
        )
    ]
    expected = RunResult(
        search_id=search.id,
        found=1,
        new=1,
        pending_auto_applies=pending,
        auto_apply_queued=1,
    )
    with (
        patch("app.worker.tasks.session_scope", test_scope),
        patch.object(PipelineService, "run", return_value=expected),
        patch("app.worker.tasks.apply_to_job_task.delay") as apply_delay,
    ):
        result = run_search_run_task(queued.id, search.user_id, search.id)
    assert result["status"] == "ready"
    apply_delay.assert_called_once_with(11, search.user_id, 22, None)
