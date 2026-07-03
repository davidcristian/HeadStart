"""SSRF guards on the shared scraper HttpClient."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.core import outbound_url
from app.core.outbound_url import UnsafeOutboundUrlError
from app.scrapers.http import HttpClient, _validate_outbound_request
from tests.conftest import make_http_client


def _no_request(_request: httpx.Request) -> httpx.Response:
    raise AssertionError("request should never be sent for a blocked URL")


def test_post_json_validates_url_upfront() -> None:
    """An injected client carries no request hook, so post_json must block SSRF itself."""
    http = make_http_client(_no_request)
    with pytest.raises(UnsafeOutboundUrlError):
        http.post_json("http://169.254.169.254/latest/meta-data/", json={})


def test_post_form_validates_url_upfront() -> None:
    http = make_http_client(_no_request)
    with pytest.raises(UnsafeOutboundUrlError):
        http.post_form("http://10.0.0.1/token", data={})


def test_redirect_to_internal_address_is_revalidated(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 302 to an internal IP must be re-checked by the per-request hook, not followed."""
    monkeypatch.setattr(outbound_url, "get_settings", lambda: SimpleNamespace(environment="local"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "169.254.169.254":
            raise AssertionError("redirect to internal address should have been blocked")
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        event_hooks={"request": [_validate_outbound_request]},
    )
    with HttpClient(client=client) as http, pytest.raises(UnsafeOutboundUrlError):
        http.get_text("http://board.test/jobs")
