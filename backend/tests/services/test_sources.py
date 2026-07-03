"""Tests for source dry-run scraping."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.user import User
from app.schemas.source import SourceCreate, SourceTestRequest, SourceUpdate
from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.services.sources import SourceService
from tests.worker.test_pipeline import _make_search, _posting


def _pro_user(db_session: Session, email: str = "src-owner@example.com") -> User:
    user = User(email=email, password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()
    return user


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


def test_create_auto_apply_requires_applier(db_session: Session) -> None:
    user = _pro_user(db_session)
    with pytest.raises(ValidationError, match="does not support auto-apply"):
        SourceService(db_session).create(
            user.id,
            SourceCreate(name="HTML", adapter_key="generic_html", auto_apply_enabled=True),
        )


def test_create_auto_apply_with_applier_adapter(db_session: Session) -> None:
    user = _pro_user(db_session)
    source = SourceService(db_session).create(
        user.id,
        SourceCreate(name="Indeed", adapter_key="indeed", auto_apply_enabled=True),
    )
    assert source.auto_apply_enabled is True


def test_update_adapter_to_non_applier_disables_auto_apply(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = SourceService(db_session)
    source = service.create(
        user.id,
        SourceCreate(name="Indeed", adapter_key="indeed", auto_apply_enabled=True),
    )

    updated = service.update(source.id, user.id, SourceUpdate(adapter_key="generic_html"))
    assert updated.adapter_key == "generic_html"
    assert updated.auto_apply_enabled is False


def test_update_enable_auto_apply_on_non_applier_rejected(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = SourceService(db_session)
    source = service.create(user.id, SourceCreate(name="HTML", adapter_key="generic_html"))

    with pytest.raises(ValidationError, match="does not support auto-apply"):
        service.update(source.id, user.id, SourceUpdate(auto_apply_enabled=True))


def test_update_adapter_to_applier_keeps_auto_apply(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = SourceService(db_session)
    source = service.create(
        user.id,
        SourceCreate(name="Indeed", adapter_key="indeed", auto_apply_enabled=True),
    )

    updated = service.update(source.id, user.id, SourceUpdate(adapter_key="linkedin"))
    assert updated.adapter_key == "linkedin"
    assert updated.auto_apply_enabled is True


def test_list_get_delete_source(db_session: Session) -> None:
    from app.core.exceptions import NotFoundError

    user = _pro_user(db_session)
    service = SourceService(db_session)
    source = service.create(user.id, SourceCreate(name="GH", adapter_key="greenhouse"))

    assert service.list_all(user.id) == [source]
    assert service.get(source.id, user.id).name == "GH"

    service.delete(source.id, user.id)
    db_session.flush()
    assert service.list_all(user.id) == []
    with pytest.raises(NotFoundError):
        service.get(source.id, user.id)


def test_create_rejects_unknown_adapter(db_session: Session) -> None:
    user = _pro_user(db_session)
    with pytest.raises(ValidationError, match="Unknown adapter_key"):
        SourceService(db_session).create(
            user.id, SourceCreate(name="Bad", adapter_key="does-not-exist")
        )


def test_detect_returns_greenhouse_defaults(db_session: Session) -> None:
    from app.schemas.source import SourceDetectRequest

    result = SourceService(db_session).detect(
        SourceDetectRequest(url="https://boards.greenhouse.io/stripe")
    )
    assert result.adapter_key == "greenhouse"
    assert result.default_config["board_token"] == "stripe"


def test_detect_unknown_url_raises(db_session: Session) -> None:
    from app.schemas.source import SourceDetectRequest

    with pytest.raises(ValidationError, match="Could not detect"):
        SourceService(db_session).detect(
            SourceDetectRequest(url="https://not-a-job-board.example.com/careers")
        )
