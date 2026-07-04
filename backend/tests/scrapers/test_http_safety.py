"""SSRF guards and request helpers on the shared scraper HttpClient."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core import outbound_url
from app.core.outbound_url import UnsafeOutboundUrlError
from app.scrapers.http import HttpClient, _prepare_outbound_request
from app.scrapers.rate_limit import RateLimiter
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
        event_hooks={"request": [_prepare_outbound_request]},
    )
    with HttpClient(client=client) as http, pytest.raises(UnsafeOutboundUrlError):
        http.get_text("http://board.test/jobs")


def _echo(payload: object) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(payload, str):
            return httpx.Response(200, text=payload)
        return httpx.Response(200, json=payload)

    return handler


def test_get_json_returns_parsed_body() -> None:
    http = make_http_client(_echo({"ok": True}))
    assert http.get_json("https://board.test/j") == {"ok": True}


def test_get_text_returns_body() -> None:
    http = make_http_client(_echo("hello"))
    assert http.get_text("https://board.test/j") == "hello"


def test_post_json_returns_parsed_body() -> None:
    http = make_http_client(_echo({"created": 1}))
    assert http.post_json("https://board.test/j", json={"a": 1}) == {"created": 1}


def test_post_form_returns_text() -> None:
    http = make_http_client(_echo("form-response"))
    assert http.post_form("https://board.test/token", data={"grant": "x"}) == "form-response"


def test_post_raw_returns_response() -> None:
    http = make_http_client(_echo("raw"))
    resp = http.post_raw("https://board.test/upload", content=b"bytes")
    assert isinstance(resp, httpx.Response)
    assert resp.text == "raw"


def test_put_json_returns_parsed_body() -> None:
    http = make_http_client(_echo({"updated": True}))
    assert http.put_json("https://board.test/j", json={"a": 1}) == {"updated": True}


def test_put_raw_returns_response() -> None:
    http = make_http_client(_echo("put-raw"))
    resp = http.put_raw("https://board.test/signed", content="bytes")
    assert isinstance(resp, httpx.Response)
    assert resp.text == "put-raw"


def test_post_multipart_returns_json_when_content_type_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"parsed": 1})

    http = make_http_client(handler)
    result = http.post_multipart("https://board.test/upload", data={"a": "1"}, files={"f": b"x"})
    assert result == {"parsed": 1}


def test_post_multipart_returns_text_when_not_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="plain-text", headers={"content-type": "text/plain"})

    http = make_http_client(handler)
    result = http.post_multipart("https://board.test/upload", data={"a": "1"}, files={"f": b"x"})
    assert result == "plain-text"


def test_close_when_owns_client_closes_underlying_client() -> None:
    """The owns-client branch (no injected client) closes the httpx.Client it built."""
    fake_client = MagicMock()
    with patch("app.scrapers.http.httpx.Client", return_value=fake_client):
        http = HttpClient()
    assert http._owns_client is True
    http.close()
    fake_client.close.assert_called_once_with()


def test_close_when_client_injected_does_not_close() -> None:
    """An injected client is owned by the caller, so close() is a no-op on it."""
    http = make_http_client(_echo({"ok": True}))
    assert http._owns_client is False
    http.close()  # should not raise; underlying client stays usable
    assert http.get_json("https://board.test/j") == {"ok": True}


def test_context_manager_closes_on_exit() -> None:
    fake_client = MagicMock()
    with patch("app.scrapers.http.httpx.Client", return_value=fake_client), HttpClient() as http:
        assert isinstance(http, HttpClient)
    fake_client.close.assert_called_once_with()


def test_wait_rate_limit_invokes_limiter_when_set() -> None:
    limiter = RateLimiter(0.5)
    http = make_http_client(_echo({"ok": True}))
    http._rate_limiter = limiter
    with patch.object(limiter, "wait") as wait:
        http.get_json("https://board.test/j")
    wait.assert_called_once_with()


def test_wait_rate_limit_noop_when_unset() -> None:
    http = make_http_client(_echo({"ok": True}))
    assert http._rate_limiter is None
    http._wait_rate_limit()  # should be a no-op and not raise
