"""Tests for Microsoft Careers shared HTTP helpers."""

import httpx
import pytest

from app.appliers.adapters.microsoft_careers_common import (
    api_error_message,
    build_http_client,
    extract_application_id,
    has_session_cookies,
    request_headers,
    resolve_csrf_token,
    resolve_position_id,
)
from app.core.outbound_url import UnsafeOutboundUrlError
from tests.conftest import make_http_client


def test_resolve_position_id_falls_back_to_external_id() -> None:
    assert resolve_position_id({}, "https://example.com/no-match", "  99 ") == "99"


def test_resolve_csrf_token_from_session() -> None:
    assert (
        resolve_csrf_token(
            {"session": {"_csrf": "sess-token"}},
            {},
            http=make_http_client(_unexpected),
            apply_url="https://ref",
        )
        == "sess-token"
    )


def test_resolve_csrf_token_from_config() -> None:
    assert (
        resolve_csrf_token(
            {"session": {}},
            {"csrf": "config-token"},
            http=make_http_client(_unexpected),
            apply_url="https://ref",
        )
        == "config-token"
    )


_APPLY_URL = "https://apply.careers.microsoft.com/careers/apply/1"


def test_resolve_csrf_token_from_apply_page_meta() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='<meta name="_csrf" content="page-token">')

    assert (
        resolve_csrf_token(None, {}, http=make_http_client(handler), apply_url=_APPLY_URL)
        == "page-token"
    )


def test_resolve_csrf_token_no_meta_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>no meta</html>")

    assert (
        resolve_csrf_token(None, {}, http=make_http_client(handler), apply_url=_APPLY_URL) is None
    )


def test_resolve_csrf_token_handles_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    assert (
        resolve_csrf_token(None, {}, http=make_http_client(handler), apply_url=_APPLY_URL) is None
    )


def test_resolve_csrf_token_propagates_non_http_errors() -> None:
    """SSRF / programming errors must not collapse into a missing-CSRF result."""
    with pytest.raises(UnsafeOutboundUrlError):
        resolve_csrf_token(
            None,
            {},
            http=make_http_client(_unexpected),
            apply_url="http://127.0.0.1/careers/apply/1",
        )


def test_build_http_client_merges_credentials() -> None:
    client = build_http_client(
        {"headers": {"X-A": "1"}, "cookies": {"c": "1"}}, headers={"X-B": "2"}
    )
    assert client is not None


def test_build_http_client_without_credentials() -> None:
    assert build_http_client(None) is not None


def test_request_headers_without_json_and_without_credentials() -> None:
    headers = request_headers(csrf_token="t", referer="https://ref", json_body=False)
    assert "Content-Type" not in headers
    assert headers["X-CSRF-Token"] == "t"


def test_request_headers_with_credentials_no_cookies() -> None:
    headers = request_headers(
        csrf_token="t",
        referer="https://ref",
        credentials={"headers": {"X-C": "3"}, "cookies": {}},
    )
    assert headers["X-C"] == "3"
    assert "Cookie" not in headers


def test_request_headers_with_cookies() -> None:
    headers = request_headers(
        csrf_token="t",
        referer="https://ref",
        credentials={"cookies": {"a": "1", "b": "2"}},
    )
    assert headers["Cookie"] == "a=1; b=2"


def test_has_session_cookies_variants() -> None:
    assert has_session_cookies(None) is False
    assert has_session_cookies({"cookies": {}}) is False
    assert has_session_cookies({"cookies": {"_vs": "x"}}) is True
    assert has_session_cookies({"cookies": {"a": "1", "b": "2"}}) is True
    assert has_session_cookies({"cookies": {"only": "1"}}) is False


def test_extract_application_id_variants() -> None:
    assert extract_application_id("nope") is None
    assert extract_application_id({"data": {"applicationId": "d-1"}}) == "d-1"
    assert extract_application_id({"data": {}}) is None
    assert extract_application_id({"application_id": "top-1"}) == "top-1"
    assert extract_application_id({}) is None


def test_api_error_message_variants() -> None:
    assert api_error_message("not a dict") is None
    assert api_error_message({"status": 200, "error": {"message": ""}, "data": {}}) is None
    assert api_error_message({"success": False, "errors": [{"message": "bad"}]}) == "bad"
    failed = "microsoft_careers apply request failed"
    assert api_error_message({"success": False, "errors": [{}]}) == failed
    assert api_error_message({"success": False, "errors": ["string"]}) == failed
    assert api_error_message({"success": False, "message": "closed req"}) == "closed req"
    assert api_error_message({"errors": [{"error": "worse"}]}) == "worse"
    assert api_error_message({"errors": [{}]}) is None
    assert api_error_message({"errors": ["string"]}) is None
    assert api_error_message({"error": {"message": "validation failed"}}) == "validation failed"
    assert api_error_message({"success": False}) == "microsoft_careers apply request failed"


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected: {request.method} {request.url}")
