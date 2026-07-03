"""Unit tests for Google Careers batchexecute transport helpers."""

from __future__ import annotations

import httpx
import pytest

from app.appliers.adapters.google_careers_batchexecute import (
    GoogleCareersRpcError,
    call_batchexecute,
    extract_rpc_result,
    extract_wiz_data,
    parse_batchexecute_response,
    rpc_error_message,
    strip_xssi,
)
from tests.conftest import make_http_client


def test_extract_wiz_data_missing_raises() -> None:
    with pytest.raises(ValueError, match="missing WIZ_global_data"):
        extract_wiz_data("<html>no wiz here</html>")


def test_extract_wiz_data_parses_object() -> None:
    assert extract_wiz_data('window.WIZ_global_data = {"a": 1};') == {"a": 1}
    assert extract_wiz_data("window.WIZ_global_data = {};") == {}
    assert extract_wiz_data('window.WIZ_global_data = {"x": [1, 2]};') == {"x": [1, 2]}


def test_strip_xssi_with_and_without_prefix() -> None:
    assert strip_xssi(")]}'\n[1,2]") == "[1,2]"
    assert strip_xssi("  [3,4]") == "[3,4]"


def test_parse_batchexecute_response_falls_back_to_full_body() -> None:
    # No line starts with '[' after splitting -> falls through to json.loads(cleaned).
    assert parse_batchexecute_response('{"k": 1}') == {"k": 1}


def test_parse_batchexecute_response_picks_last_array_line() -> None:
    body = ')]}\'\ngarbage\n["wrb.fr","x","[]"]'
    parsed = parse_batchexecute_response(body)
    assert parsed[0] == "wrb.fr"


def test_rpc_error_message_non_list_returns_none() -> None:
    assert rpc_error_message({"not": "list"}) is None


def test_rpc_error_message_finds_error() -> None:
    payload = [["er", 0, 0, "fallback", 0, "boom", 0, 1]]
    assert rpc_error_message(payload) == "boom"


def test_rpc_error_message_uses_fallback_when_index5_falsy() -> None:
    payload = [["er", 0, 0, "fallback", 0, None, 0, 1]]
    assert rpc_error_message(payload) == "fallback"


def test_rpc_error_message_skips_short_items() -> None:
    payload = [["short"], "not-a-list", ["er", 1, 2, 3, 4, 5, 6, 7]]
    assert rpc_error_message(payload) == "5"


def test_rpc_error_message_skips_long_non_error_items() -> None:
    # A long item (>=8) whose head is not "er" must be skipped (loop continues).
    payload = [
        ["wrb.fr", 1, 2, 3, 4, 5, 6, 7],
        ["er", 1, 2, 3, 4, "the-error", 6, 7],
    ]
    assert rpc_error_message(payload) == "the-error"


def test_extract_rpc_result_not_list_raises() -> None:
    with pytest.raises(GoogleCareersRpcError, match="was not a list"):
        extract_rpc_result({"x": 1}, "rpc")


def test_extract_rpc_result_error_envelope_raises() -> None:
    payload = [["er", 0, 0, "fallback", 0, "explode", 0, 1]]
    with pytest.raises(GoogleCareersRpcError, match="explode"):
        extract_rpc_result(payload, "rpc")


def test_extract_rpc_result_missing_rpc_raises() -> None:
    payload = [["wrb.fr", "other", "[]"]]
    with pytest.raises(GoogleCareersRpcError, match="missing from response"):
        extract_rpc_result(payload, "rpc")


def test_extract_rpc_result_skips_bad_items_and_decodes_string() -> None:
    payload = [
        "not-a-list",
        ["too", "short"],
        ["notwrb", "rpc", "[]"],
        ["wrb.fr", "rpc", '{"packetId": "p1"}'],
    ]
    assert extract_rpc_result(payload, "rpc") == {"packetId": "p1"}


def test_extract_rpc_result_returns_raw_when_not_string() -> None:
    payload = [["wrb.fr", "rpc", {"already": "parsed"}]]
    assert extract_rpc_result(payload, "rpc") == {"already": "parsed"}


def test_call_batchexecute_without_fdrfje() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=')]}\'\n[["wrb.fr","rpc","{}"]]')

    result = call_batchexecute(
        make_http_client(handler),
        rpc_id="rpc",
        args=[{"a": 1}],
        wiz={"cfb2h": "bl-token"},  # no FdrFJe -> f.sid omitted
        at_token="tok",
        source_path="/about/careers/applications/apply",
    )
    assert result == {}
    assert "f.sid" not in str(seen["url"])


def test_call_batchexecute_with_fdrfje_and_extra_headers() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["header"] = request.headers.get("X-Extra")
        return httpx.Response(200, text=')]}\'\n[["wrb.fr","rpc","{}"]]')

    call_batchexecute(
        make_http_client(handler),
        rpc_id="rpc",
        args=[{"a": 1}],
        wiz={"cfb2h": "bl", "FdrFJe": "sid-123"},
        at_token="tok",
        source_path="/apply",
        extra_headers={"X-Extra": "1"},
    )
    assert "f.sid=sid-123" in str(seen["url"])
    assert seen["header"] == "1"
