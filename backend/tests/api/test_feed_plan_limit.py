"""The RSS feed endpoint must reject users whose plan lacks feed access."""

from __future__ import annotations

import contextlib
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.models.user import User
from app.repositories.users import UserRepository
from app.services.feed import FeedService


@contextmanager
def _client_db():
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    try:
        yield db
        db.commit()
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)


def test_rss_feed_rejects_plan_without_feed_access(client: TestClient) -> None:
    """A valid token for a free-plan user still 402s: RSS is a paid feature."""
    with _client_db() as db:
        user = UserRepository(db).add(
            User(email="free-feed@example.com", password_hash="x", plan="free")
        )
        token = FeedService(db).issue_token(user)

    resp = client.get(f"/api/v1/feed/rss?token={token}")
    assert resp.status_code == 402
    body = resp.json()
    assert body["detail"]
    assert body["code"] == "rss_feed"
    assert body["plan"] == "free"
    assert "limit" in body
