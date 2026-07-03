"""Outbound URL policy for Playwright navigations and subresource fetches."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.outbound_url import UnsafeOutboundUrlError, assert_safe_outbound_url


def install_playwright_outbound_guard(page: Any) -> Callable[[], None]:
    """Reject disallowed request URLs before Playwright follows redirects or loads assets."""
    violations: list[str] = []

    def _on_route(route: Any) -> None:
        try:
            assert_safe_outbound_url(route.request.url)
        except UnsafeOutboundUrlError as exc:
            violations.append(str(exc))
            route.abort()
            return
        route.continue_()

    page.route("**/*", _on_route)

    def assert_no_violations() -> None:
        if violations:
            raise ValueError(violations[0])

    return assert_no_violations
