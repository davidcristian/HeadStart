"""RSS feed token management and feed assembly."""

from __future__ import annotations

from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import TokenError, create_feed_token, decode_feed_token
from app.models.user import User
from app.repositories.users import UserRepository
from app.services.jobs import JobService
from app.services.rss import RssChannel, build_rss_feed


class FeedService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.jobs = JobService(session)

    def issue_token(self, user: User) -> str:
        """Return a signed feed token for the user's current version."""
        return create_feed_token(user.id, version=user.feed_token_version)

    def rotate_token(self, user: User) -> str:
        """Invalidate prior feed URLs and return a new signed feed token."""
        self.users.bump_feed_token_version(user)
        return self.issue_token(user)

    def resolve_user(self, token: str) -> User | None:
        """Resolve an active user from a signed feed token."""
        try:
            payload = decode_feed_token(token)
        except TokenError:
            return None
        user = self.users.get(int(payload["sub"]))
        if user is None or not user.is_active:
            return None
        if int(payload["ver"]) != user.feed_token_version:
            return None
        return user

    def build_feed_url(
        self,
        *,
        base_url: str,
        token: str,
        search_id: int | None = None,
        status: str | None = None,
    ) -> str:
        """Build the absolute RSS feed URL with optional filters."""
        params: dict[str, str] = {"token": token}
        if search_id is not None:
            params["search_id"] = str(search_id)
        if status is not None:
            params["status"] = status
        query = urlencode(params)
        return f"{base_url.rstrip('/')}/api/v1/feed/rss?{query}"

    def render_rss(
        self,
        user: User,
        *,
        feed_url: str,
        search_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> str:
        """Build the RSS XML for a user's jobs."""
        if search_id is not None and not self._search_owned_by_user(search_id, user.id):
            raise NotFoundError(f"Search {search_id} not found")
        jobs = self.jobs.list_all(user_id=user.id, search_id=search_id, status=status, limit=limit)
        channel = RssChannel(
            title="HeadStart jobs",
            link=feed_url,
            description="Jobs discovered by your HeadStart searches.",
            jobs=jobs,
        )
        return build_rss_feed(channel)

    def _search_owned_by_user(self, search_id: int, user_id: int) -> bool:
        from app.repositories.searches import SearchRepository

        return SearchRepository(self.session).get(search_id, user_id) is not None
