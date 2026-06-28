"""Tests for source dry-run scraping."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.schemas.source import SourceTestRequest
from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.services.sources import SourceService
from tests.worker.test_pipeline import _make_search, _posting


def test_source_test_returns_sample_without_persisting(db_session: Session) -> None:
    search = _make_search(db_session)
    source = search.source
    source.base_url = "https://boards.example.test/acme"
    source.default_config = {"board_token": "acme", "company": "ACME"}
    db_session.flush()

    captured: dict[str, object] = {}

    def fake_scrape(self, **kwargs: object) -> list[JobPosting]:
        captured.update(kwargs)
        return [_posting("1"), _posting("2"), _posting("3")]

    with patch.object(PipelineService, "scrape", fake_scrape):
        result = SourceService(db_session).test_scrape(
            source.id, search.user_id, SourceTestRequest()
        )

    assert result.ok is True
    assert result.error is None
    assert result.found == 3
    assert len(result.sample) == 3
    assert result.sample[0].title == "Job 1"
    assert captured["query_url"] == "https://boards.example.test/acme"
    assert captured["config"] == {"board_token": "acme", "company": "ACME"}


def test_source_test_surfaces_scrape_errors(db_session: Session) -> None:
    search = _make_search(db_session)
    source = search.source
    db_session.flush()

    def failing_scrape(self, **kwargs: object) -> list[JobPosting]:
        raise ValueError("selector not found")

    with patch.object(PipelineService, "scrape", failing_scrape):
        result = SourceService(db_session).test_scrape(
            source.id, search.user_id, SourceTestRequest()
        )

    assert result.ok is False
    assert result.found == 0
    assert result.sample == []
    assert result.error == "selector not found"
