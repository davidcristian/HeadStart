"""Tests for immediate search runs."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.services.pipeline import PipelineService, RunResult
from app.services.searches import SearchService
from tests.worker.test_pipeline import _make_search


def test_run_now_returns_pipeline_summary(db_session: Session) -> None:
    search = _make_search(db_session)
    expected = RunResult(search_id=search.id, found=2, new=1, notified=1, failed=0, error=None)

    with patch.object(PipelineService, "run", return_value=expected):
        result = SearchService(db_session).run_now(search.id, search.user_id)

    assert result.search_id == search.id
    assert result.found == 2
    assert result.new == 1
    assert result.notified == 1
    assert result.failed == 0
    assert result.error is None
