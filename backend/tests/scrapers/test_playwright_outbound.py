"""Tests for Playwright outbound URL guarding."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.scrapers.playwright_outbound import install_playwright_outbound_guard


def test_guard_allows_public_request(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MagicMock()
    handler = None

    def capture_route(pattern: str, route_handler: object) -> None:
        nonlocal handler
        handler = route_handler

    page.route.side_effect = capture_route
    monkeypatch.setattr(
        "app.scrapers.playwright_outbound.pin_outbound_request",
        lambda url: type(
            "Pinned",
            (),
            {"request_url": url, "host_header": "example.com"},
        )(),
    )
    assert_no_violations = install_playwright_outbound_guard(page)

    route = MagicMock()
    route.request.url = "https://example.com/jobs"
    route.request.headers = {"user-agent": "test"}
    assert handler is not None
    handler(route)

    route.continue_.assert_called_once_with()
    route.abort.assert_not_called()
    assert_no_violations()


def test_guard_pins_request_to_validated_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MagicMock()
    handler = None

    def capture_route(pattern: str, route_handler: object) -> None:
        nonlocal handler
        handler = route_handler

    page.route.side_effect = capture_route
    monkeypatch.setattr(
        "app.scrapers.playwright_outbound.pin_outbound_request",
        lambda url: type(
            "Pinned",
            (),
            {"request_url": "https://93.184.216.34/jobs", "host_header": "example.com"},
        )(),
    )
    install_playwright_outbound_guard(page)

    route = MagicMock()
    route.request.url = "https://example.com/jobs"
    route.request.headers = {"user-agent": "test"}
    assert handler is not None
    handler(route)

    route.continue_.assert_called_once_with(
        url="https://93.184.216.34/jobs",
        headers={"user-agent": "test", "Host": "example.com"},
    )
    route.abort.assert_not_called()


def test_guard_blocks_internal_redirect_target(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MagicMock()
    handler = None

    def capture_route(pattern: str, route_handler: object) -> None:
        nonlocal handler
        handler = route_handler

    page.route.side_effect = capture_route

    from app.core.outbound_url import UnsafeOutboundUrlError

    def _reject(url: str) -> None:
        raise UnsafeOutboundUrlError(f"Hostname in {url} resolves to a disallowed address.")

    monkeypatch.setattr("app.scrapers.playwright_outbound.pin_outbound_request", _reject)
    assert_no_violations = install_playwright_outbound_guard(page)

    route = MagicMock()
    route.request.url = "http://169.254.169.254/latest/meta-data/"
    assert handler is not None
    handler(route)

    route.abort.assert_called_once()
    route.continue_.assert_not_called()
    with pytest.raises(ValueError, match="169.254.169.254"):
        assert_no_violations()
