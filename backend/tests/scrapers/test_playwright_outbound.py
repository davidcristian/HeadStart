"""Tests for Playwright outbound URL guarding."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.scrapers.playwright_outbound import install_playwright_outbound_guard


def test_guard_allows_public_request() -> None:
    page = MagicMock()
    handler = None

    def capture_route(pattern: str, route_handler: object) -> None:
        nonlocal handler
        handler = route_handler

    page.route.side_effect = capture_route
    assert_no_violations = install_playwright_outbound_guard(page)

    route = MagicMock()
    route.request.url = "https://example.com/jobs"
    assert handler is not None
    handler(route)

    route.continue_.assert_called_once()
    route.abort.assert_not_called()
    assert_no_violations()


def test_guard_blocks_internal_redirect_target() -> None:
    page = MagicMock()
    handler = None

    def capture_route(pattern: str, route_handler: object) -> None:
        nonlocal handler
        handler = route_handler

    page.route.side_effect = capture_route
    assert_no_violations = install_playwright_outbound_guard(page)

    route = MagicMock()
    route.request.url = "http://169.254.169.254/latest/meta-data/"
    assert handler is not None
    handler(route)

    route.abort.assert_called_once()
    route.continue_.assert_not_called()
    with pytest.raises(ValueError, match="169.254.169.254"):
        assert_no_violations()
