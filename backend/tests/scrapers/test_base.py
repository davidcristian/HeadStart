"""Tests for the scraper base class and registry."""

from __future__ import annotations

import pytest

from app.scrapers import base
from app.scrapers.base import (
    Scraper,
    available_scrapers,
    get_scraper,
    register_scraper,
)
from app.scrapers.http import HttpClient
from app.scrapers.types import JobPosting, ScrapeContext
from tests.conftest import make_http_client


def _noop_handler(request):  # pragma: no cover - never invoked
    raise AssertionError("no request should be sent")


class _StubScraper(Scraper):
    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        return []


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Snapshot and restore the module-level registry around each test.

    Import the adapters package first so built-ins are present in the snapshot;
    otherwise a test that registers before the (one-time) adapter import could
    have its teardown erase the built-ins for later tests.
    """
    import app.scrapers.adapters  # noqa: F401

    saved = dict(base._REGISTRY)
    try:
        yield
    finally:
        base._REGISTRY.clear()
        base._REGISTRY.update(saved)


def test_init_builds_default_http_client_when_none_injected() -> None:
    scraper = _StubScraper()
    assert isinstance(scraper.http, HttpClient)
    assert scraper._rate_limiter is None


def test_init_uses_injected_http_client() -> None:
    http = make_http_client(_noop_handler)
    scraper = _StubScraper(http=http)
    assert scraper.http is http


def test_register_scraper_registers_class() -> None:
    @register_scraper("test_key_reg")
    class Adapter(_StubScraper):
        pass

    assert base._REGISTRY["test_key_reg"] is Adapter


def test_register_scraper_duplicate_key_raises() -> None:
    @register_scraper("dup_key")
    class First(_StubScraper):
        pass

    with pytest.raises(ValueError, match="dup_key.*already registered"):

        @register_scraper("dup_key")
        class Second(_StubScraper):
            pass


def test_register_scraper_same_class_reregistration_is_noop() -> None:
    @register_scraper("reregister_key")
    class Adapter(_StubScraper):
        pass

    # Re-registering the identical class under the same key must not raise.
    register_scraper("reregister_key")(Adapter)
    assert base._REGISTRY["reregister_key"] is Adapter


def test_get_scraper_returns_instance_for_known_key() -> None:
    @register_scraper("get_key")
    class Adapter(_StubScraper):
        pass

    scraper = get_scraper("get_key")
    assert isinstance(scraper, Adapter)


def test_get_scraper_passes_http_and_rate_limiter() -> None:
    from app.scrapers.rate_limit import RateLimiter

    @register_scraper("get_key_args")
    class Adapter(_StubScraper):
        pass

    http = make_http_client(_noop_handler)
    limiter = RateLimiter(0.0)
    scraper = get_scraper("get_key_args", http=http, rate_limiter=limiter)
    assert isinstance(scraper, Adapter)
    assert scraper.http is http
    assert scraper._rate_limiter is limiter


def test_get_scraper_unknown_key_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="No scraper registered for 'does_not_exist'"):
        get_scraper("does_not_exist")


def test_available_scrapers_returns_sorted_keys() -> None:
    keys = available_scrapers()
    assert keys == sorted(keys)
    assert "greenhouse" in keys
