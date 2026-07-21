"""Unit tests for Meta Careers GraphQL client and live-submit helpers."""

from __future__ import annotations

import json

import httpx
import pytest

from app.appliers.adapters.meta_careers_graphql import (
    _parse_graphql_json,
    post_graphql_multipart,
)
from app.appliers.adapters.meta_careers_live import (
    external_application_id,
    resolve_lsd_token,
)
from app.scrapers.http import HttpClient
from tests.conftest import make_http_client


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")


# --- _parse_graphql_json -----------------------------------------------------


def test_parse_graphql_json_invalid_json() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_graphql_json("not json")


def test_parse_graphql_json_non_dict() -> None:
    with pytest.raises(ValueError, match="unexpected payload"):
        _parse_graphql_json("[1, 2]")


def test_parse_graphql_json_error_with_message() -> None:
    body = json.dumps({"errors": [{"message": "  boom  "}]})
    with pytest.raises(ValueError, match="GraphQL error: boom"):
        _parse_graphql_json(body)


def test_parse_graphql_json_error_without_message() -> None:
    body = json.dumps({"errors": [{"code": 1}]})
    with pytest.raises(ValueError, match="returned errors"):
        _parse_graphql_json(body)


def test_parse_graphql_json_error_first_not_dict() -> None:
    body = json.dumps({"errors": ["a string error"]})
    with pytest.raises(ValueError, match="returned errors"):
        _parse_graphql_json(body)


def test_parse_graphql_json_error_blank_message() -> None:
    body = json.dumps({"errors": [{"message": "   "}]})
    with pytest.raises(ValueError, match="returned errors"):
        _parse_graphql_json(body)


def test_parse_graphql_json_success() -> None:
    assert _parse_graphql_json('{"data": {"ok": 1}}') == {"data": {"ok": 1}}


# --- post_graphql_multipart --------------------------------------------------


def test_post_graphql_multipart_returns_dict_directly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": {"x": 1}}, headers={"content-type": "application/json"}
        )

    result = post_graphql_multipart(
        make_http_client(handler),
        lsd="l",
        friendly_name="Q",
        doc_id="1",
        variables={"input": {}},
        uploadables={"candidateResumeFile": ("r.pdf", b"%PDF", "application/pdf")},
    )
    assert result == {"data": {"x": 1}}


def test_post_graphql_multipart_rejects_dict_error_envelope() -> None:
    """Resume multipart must fail on GraphQL errors like the JSON path."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errors": [{"message": "  resume rejected  "}]},
            headers={"content-type": "application/json"},
        )

    with pytest.raises(ValueError, match="GraphQL error: resume rejected"):
        post_graphql_multipart(
            make_http_client(handler),
            lsd="l",
            friendly_name="Q",
            doc_id="1",
            variables={"input": {}},
            uploadables={"candidateResumeFile": ("r.pdf", b"%PDF", "application/pdf")},
        )


def test_post_graphql_multipart_parses_string_response(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force post_multipart to return a non-dict string so the parse branch runs.
    def fake_post_multipart(self: HttpClient, url: str, **kwargs: object) -> object:
        return '{"data": {"y": 2}}'

    monkeypatch.setattr(HttpClient, "post_multipart", fake_post_multipart)
    result = post_graphql_multipart(
        make_http_client(_unexpected),
        lsd="l",
        friendly_name="Q",
        doc_id="1",
        variables={"input": {}},
        uploadables={"candidateResumeFile": ("r.pdf", b"%PDF", "application/pdf")},
    )
    assert result == {"data": {"y": 2}}


def test_post_graphql_multipart_rejects_string_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post_multipart(self: HttpClient, url: str, **kwargs: object) -> object:
        return '{"errors": [{"message": "string path boom"}]}'

    monkeypatch.setattr(HttpClient, "post_multipart", fake_post_multipart)
    with pytest.raises(ValueError, match="GraphQL error: string path boom"):
        post_graphql_multipart(
            make_http_client(_unexpected),
            lsd="l",
            friendly_name="Q",
            doc_id="1",
            variables={"input": {}},
            uploadables={"candidateResumeFile": ("r.pdf", b"%PDF", "application/pdf")},
        )


# --- resolve_lsd_token -------------------------------------------------------


def test_resolve_lsd_token_from_session() -> None:
    creds = {"session": {"lsd": "sess-lsd"}, "cookies": {}}
    assert (
        resolve_lsd_token(make_http_client(_unexpected), creds, {}, requisition_id="1")
        == "sess-lsd"
    )


def test_resolve_lsd_token_session_blank_then_config() -> None:
    # session has the key but falsy -> loop continues, falls to config.
    creds = {"session": {"lsd": "", "csrf_token": ""}, "cookies": {}}
    assert (
        resolve_lsd_token(
            make_http_client(_unexpected), creds, {"csrf_token": "cfg-lsd"}, requisition_id="1"
        )
        == "cfg-lsd"
    )


def test_resolve_lsd_token_fetches_from_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Apply page HTML with an lsd token embedded.
        return httpx.Response(200, text='<input name="lsd" value="fetched-lsd">')

    token = resolve_lsd_token(
        make_http_client(handler), None, {}, requisition_id="2132019417725760"
    )
    assert token == "fetched-lsd"


# --- external_application_id -------------------------------------------------


def test_external_application_id_delegates() -> None:
    resp = {"data": {"xcp_create_application_v2": {"application_id": "a-1"}}}
    assert external_application_id(resp) == "a-1"
