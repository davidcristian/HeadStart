"""Outbound URL policy for Playwright navigations and subresource fetches."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.outbound_url import UnsafeOutboundUrlError, pin_outbound_request


def install_playwright_outbound_guard(page: Any) -> Callable[[], None]:
    """Reject disallowed URLs and pin each request to the validated IP before connect.

    Playwright/Chromium would otherwise re-resolve DNS after our SSRF check. Rewriting
    the request URL to the checked IP (with the original Host header) closes that
    rebinding window. Pages must allow HTTPS errors when connecting by IP literal
    (certificate SANs name the hostname, not the pinned address).
    """
    violations: list[str] = []

    def _on_route(route: Any) -> None:
        try:
            pinned = pin_outbound_request(route.request.url)
        except UnsafeOutboundUrlError as exc:
            violations.append(str(exc))
            route.abort()
            return
        if pinned.request_url == route.request.url:
            route.continue_()
            return
        headers = dict(route.request.headers)
        headers["Host"] = pinned.host_header
        route.continue_(url=pinned.request_url, headers=headers)

    page.route("**/*", _on_route)

    def assert_no_violations() -> None:
        if violations:
            raise ValueError(violations[0])

    return assert_no_violations
