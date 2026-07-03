"""Tests for RSS feed token management."""

import pytest

from app.core.exceptions import NotFoundError
from app.services.feed import FeedService


def test_issue_and_resolve_feed_token(db_session) -> None:
    from tests.worker.test_pipeline import _make_search

    search = _make_search(db_session)
    service = FeedService(db_session)

    token = service.issue_token(search.user)
    user = service.resolve_user(token)

    assert user is not None
    assert user.id == search.user_id


def test_rotate_invalidates_previous_feed_token(db_session) -> None:
    from tests.worker.test_pipeline import _make_search

    search = _make_search(db_session)
    service = FeedService(db_session)

    old_token = service.issue_token(search.user)
    new_token = service.rotate_token(search.user)

    assert service.resolve_user(old_token) is None
    assert service.resolve_user(new_token) is not None


def test_build_feed_url_includes_filters(db_session) -> None:
    service = FeedService(db_session)
    url = service.build_feed_url(
        base_url="http://localhost:8000",
        token="signed-token",
        search_id=5,
        status="new",
    )

    assert "token=signed-token" in url
    assert "search_id=5" in url
    assert "status=new" in url


def test_build_feed_url_without_filters(db_session) -> None:
    service = FeedService(db_session)
    url = service.build_feed_url(base_url="http://localhost:8000/", token="tok")
    assert url == "http://localhost:8000/api/v1/feed/rss?token=tok"


def test_resolve_user_invalid_token_returns_none(db_session) -> None:
    assert FeedService(db_session).resolve_user("not-a-real-token") is None


def test_resolve_user_inactive_returns_none(db_session) -> None:
    from tests.worker.pipeline_helpers import make_search

    search = make_search(db_session)
    service = FeedService(db_session)
    token = service.issue_token(search.user)

    search.user.is_active = False
    db_session.flush()

    assert service.resolve_user(token) is None


def test_render_rss_for_owned_search(db_session) -> None:
    from tests.worker.pipeline_helpers import make_search

    search = make_search(db_session)
    service = FeedService(db_session)

    xml = service.render_rss(search.user, feed_url="http://f/rss", search_id=search.id)
    assert "<rss" in xml


def test_render_rss_rejects_unowned_search(db_session) -> None:
    from tests.worker.pipeline_helpers import make_search

    search = make_search(db_session)
    service = FeedService(db_session)

    with pytest.raises(NotFoundError):
        service.render_rss(search.user, feed_url="http://f/rss", search_id=999999)
