"""Pinned outbound HTTP helpers shared by scrapers and notifiers."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.outbound_url import pin_outbound_request


def apply_outbound_pin(request: httpx.Request) -> None:
    """Rewrite a request URL to a resolved IP and set Host + TLS SNI to the original name.

    Connecting by IP prevents httpx from re-resolving DNS at connect time (rebinding
    TOCTOU). Host and sni_hostname keep virtual-host routing and certificate checks
    tied to the hostname that was validated.
    """
    pinned = pin_outbound_request(str(request.url))
    if pinned.request_url != str(request.url):
        request.url = httpx.URL(pinned.request_url)
    request.headers["Host"] = pinned.host_header
    if urlparse(pinned.request_url).scheme == "https":
        request.extensions["sni_hostname"] = pinned.host_header


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
    extensions = dict(kwargs.pop("extensions", None) or {})
    if urlparse(pinned.request_url).scheme == "https":
        extensions["sni_hostname"] = pinned.host_header
    return client.request(
        method,
        pinned.request_url,
        headers=headers,
        extensions=extensions,
        **kwargs,
    )
