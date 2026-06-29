"""Tests for RSS feed token management."""

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
