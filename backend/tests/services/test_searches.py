"""Service tests for search CRUD business logic."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.notification_target import NotificationTarget
from app.models.source import Source
from app.schemas.search import SearchCreate, SearchUpdate
from app.services.searches import SearchService
from tests.worker.pipeline_helpers import make_user


def _source_and_target(session: Session, user_id: int) -> tuple[int, int]:
    source = Source(
        user_id=user_id, name="src", adapter_key="greenhouse", base_url="", default_config={}
    )
    target = NotificationTarget(user_id=user_id, name="tgt", type="ntfy", config={"topic": "x"})
    session.add_all([source, target])
    session.flush()
    return source.id, target.id


def _create_data(source_id: int, target_id: int, **overrides) -> SearchCreate:
    data = {
        "name": "search",
        "source_id": source_id,
        "target_id": target_id,
        "query_url": "https://example.test",
        "filters": {},
        "config": {},
        "interval_seconds": 300,
    }
    data.update(overrides)
    return SearchCreate(**data)


def test_get_raises_when_missing(db_session: Session) -> None:
    user = make_user(db_session)
    with pytest.raises(NotFoundError, match="not found"):
        SearchService(db_session).get(999, user.id)


def test_create_and_read_round_trip(db_session: Session) -> None:
    user = make_user(db_session)
    source_id, target_id = _source_and_target(db_session, user.id)
    service = SearchService(db_session)

    created = service.create_read(user.id, _create_data(source_id, target_id))
    assert created.name == "search"

    read = service.get_read(created.id, user.id)
    assert read.id == created.id

    all_reads = service.list_reads(user.id)
    assert len(all_reads) == 1


def test_create_digest_mode_for_admin(db_session: Session) -> None:
    user = make_user(db_session)  # admin -> plan gates bypassed
    source_id, target_id = _source_and_target(db_session, user.id)
    created = SearchService(db_session).create(
        user.id,
        _create_data(source_id, target_id, notification_mode="digest", digest_interval_seconds=120),
    )
    assert created.notification_mode == "digest"


def test_create_rejects_missing_source(db_session: Session) -> None:
    user = make_user(db_session)
    _source_id, target_id = _source_and_target(db_session, user.id)
    with pytest.raises(ValidationError, match="Source"):
        SearchService(db_session).create(user.id, _create_data(999999, target_id))


def test_create_rejects_missing_target(db_session: Session) -> None:
    user = make_user(db_session)
    source_id, _target_id = _source_and_target(db_session, user.id)
    with pytest.raises(ValidationError, match="target"):
        SearchService(db_session).create(user.id, _create_data(source_id, 999999))


def test_update_changes_fields(db_session: Session) -> None:
    user = make_user(db_session)
    source_id, target_id = _source_and_target(db_session, user.id)
    service = SearchService(db_session)
    created = service.create(user.id, _create_data(source_id, target_id))

    updated = service.update_read(
        created.id,
        user.id,
        SearchUpdate(name="renamed", interval_seconds=600),
    )
    assert updated.name == "renamed"
    assert updated.interval_seconds == 600


def test_update_digest_mode_and_target_validation(db_session: Session) -> None:
    user = make_user(db_session)
    source_id, target_id = _source_and_target(db_session, user.id)
    service = SearchService(db_session)
    created = service.create(user.id, _create_data(source_id, target_id))

    updated = service.update(
        created.id,
        user.id,
        SearchUpdate(notification_mode="digest", target_id=target_id),
    )
    assert updated.notification_mode == "digest"


def test_update_rejects_invalid_target(db_session: Session) -> None:
    user = make_user(db_session)
    source_id, target_id = _source_and_target(db_session, user.id)
    service = SearchService(db_session)
    created = service.create(user.id, _create_data(source_id, target_id))

    with pytest.raises(ValidationError, match="target"):
        service.update(created.id, user.id, SearchUpdate(target_id=999999))


def test_delete_removes_search(db_session: Session) -> None:
    user = make_user(db_session)
    source_id, target_id = _source_and_target(db_session, user.id)
    service = SearchService(db_session)
    created = service.create(user.id, _create_data(source_id, target_id))

    service.delete(created.id, user.id)
    db_session.flush()

    with pytest.raises(NotFoundError):
        service.get(created.id, user.id)


def test_list_all_returns_models(db_session: Session) -> None:
    user = make_user(db_session)
    source_id, target_id = _source_and_target(db_session, user.id)
    service = SearchService(db_session)
    service.create(user.id, _create_data(source_id, target_id))

    searches = service.list_all(user.id)
    assert len(searches) == 1
