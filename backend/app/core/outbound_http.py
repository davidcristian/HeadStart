"""Pinned outbound HTTP helpers shared by scrapers and notifiers."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.outbound_url import pin_outbound_request


def apply_outbound_pin(request: httpx.Request) -> None:
    """Rewrite a request URL to a resolved IP and set the original Host header."""
    pinned = pin_outbound_request(str(request.url))
    if pinned.request_url != str(request.url):
        request.url = httpx.URL(pinned.request_url)
    request.headers["Host"] = pinned.host_header


def pinned_request(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """Issue one outbound request using a single DNS resolution for the connect."""
    pinned = pin_outbound_request(url)
    headers = dict(kwargs.pop("headers", None) or {})
    headers["Host"] = pinned.host_header
    return client.request(method, pinned.request_url, headers=headers, **kwargs)
