"""Tests for per-adapter scrape rate limiting."""

from unittest.mock import patch

import httpx
import pytest

from app.scrapers.http import HttpClient
from app.scrapers.rate_limit import CONFIG_KEY, RateLimiter, resolve_min_interval
from app.scrapers.types import ScrapeContext
from tests.conftest import make_http_client


def test_rate_limiter_waits_between_requests() -> None:
    limiter = RateLimiter(1.0)
    times = [0.0, 0.2, 1.3]

    with (
        patch("app.scrapers.rate_limit.time.monotonic", side_effect=times),
        patch("app.scrapers.rate_limit.time.sleep") as sleep,
    ):
        limiter.wait()
        limiter.wait()

    sleep.assert_called_once_with(0.8)


def test_rate_limiter_zero_interval_is_noop() -> None:
    limiter = RateLimiter(0.0)
    with patch("app.scrapers.rate_limit.time.sleep") as sleep:
        limiter.wait()
        limiter.wait()
    sleep.assert_not_called()


def test_resolve_min_interval_uses_config_override() -> None:
    assert resolve_min_interval("greenhouse", {CONFIG_KEY: 3.5}) == 3.5


def test_resolve_min_interval_falls_back_to_adapter_default() -> None:
    assert resolve_min_interval("greenhouse", {}) == 1.0
    assert resolve_min_interval("unknown_adapter", {}) == 0.0


def test_resolve_min_interval_rejects_invalid_config() -> None:
    with pytest.raises(ValueError, match=CONFIG_KEY):
        resolve_min_interval("greenhouse", {CONFIG_KEY: -1})
    with pytest.raises(ValueError, match=CONFIG_KEY):
        resolve_min_interval("greenhouse", {CONFIG_KEY: "fast"})


def test_http_client_applies_rate_limiter() -> None:
    calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1.0)
        return httpx.Response(200, json={"ok": True})

    limiter = RateLimiter(0.5)
    client = make_http_client(handler)
    client._rate_limiter = limiter  # inject without changing fixture signature

    with patch.object(limiter, "wait", wraps=limiter.wait) as wait:
        client.get_json("https://example.test/a")
        client.get_json("https://example.test/b")

    assert wait.call_count == 2
    assert len(calls) == 2


def test_pipeline_passes_rate_limited_http_client(db_session) -> None:
    from app.models.notification_target import NotificationTarget
    from app.models.search import Search
    from app.models.source import Source
    from app.models.user import User
    from app.services.pipeline import PipelineService

    user = User(email="rate@example.test", password_hash="x", is_admin=False, is_active=True)
    db_session.add(user)
    db_session.flush()
    source = Source(
        user_id=user.id,
        name="src",
        adapter_key="greenhouse",
        base_url="",
        default_config={CONFIG_KEY: 2.0},
    )
    target = NotificationTarget(user_id=user.id, name="tgt", type="ntfy", config={"topic": "x"})
    db_session.add_all([source, target])
    db_session.flush()
    search = Search(
        user_id=user.id,
        name="search",
        source_id=source.id,
        target_id=target.id,
        query_url="",
        filters={},
        config={},
        interval_seconds=300,
        enabled=True,
    )
    db_session.add(search)
    db_session.flush()

    received: dict[str, object] = {}

    class FakeScraper:
        def fetch(self, ctx: ScrapeContext) -> list:
            return []

    def factory(key: str, http: HttpClient | None = None, rate_limiter=None) -> FakeScraper:
        received["http"] = http
        received["rate_limiter"] = rate_limiter
        return FakeScraper()

    PipelineService(db_session, scraper_factory=factory).run(search.id)  # type: ignore[arg-type]

    assert received["http"] is not None
    assert received["rate_limiter"] is not None
    assert received["rate_limiter"].min_interval_seconds == 2.0  # type: ignore[union-attr]
