"""Meta Careers Relay GraphQL client helpers for apply adapters."""

from __future__ import annotations

import json
from typing import Any

from app.appliers.adapters.meta_careers_common import (
    _GRAPHQL_PATH,
    _ORIGIN,
    request_headers,
)
from app.scrapers.adapters.meta_careers_graphql import extract_lsd_token
from app.scrapers.http import HttpClient


def fetch_lsd_token(http: HttpClient, page_url: str) -> str:
    """Load a Meta careers page and return its short-lived ``lsd`` token."""
    html = http.get_text(page_url)
    return extract_lsd_token(html)


def post_graphql(
    http: HttpClient,
    *,
    lsd: str,
    friendly_name: str,
    doc_id: str,
    variables: dict[str, Any],
    credentials: dict[str, dict[str, str]] | None = None,
    referer: str | None = None,
) -> dict[str, Any]:
    """POST a persisted Relay GraphQL operation and parse the JSON body."""
    body = http.post_form(
        f"{_ORIGIN}{_GRAPHQL_PATH}",
        data={
            "lsd": lsd,
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": friendly_name,
            "variables": json.dumps(variables, separators=(",", ":")),
            "doc_id": doc_id,
        },
        headers=_request_headers(
            credentials,
            lsd=lsd,
            friendly_name=friendly_name,
            referer=referer,
        ),
    )
    return _parse_graphql_json(body)


def post_graphql_multipart(
    http: HttpClient,
    *,
    lsd: str,
    friendly_name: str,
    doc_id: str,
    variables: dict[str, Any],
    uploadables: dict[str, tuple[str, bytes, str]],
    credentials: dict[str, dict[str, str]] | None = None,
    referer: str | None = None,
) -> dict[str, Any]:
    """POST a Relay mutation with file uploadables (resume attachments)."""
    operations = {
        "doc_id": doc_id,
        "variables": variables,
    }
    file_map = {key: [f"variables.input.{key}"] for key in uploadables}
    files: dict[str, tuple[str, bytes, str]] = {}
    data: dict[str, str] = {
        "lsd": lsd,
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": friendly_name,
        "operations": json.dumps(operations, separators=(",", ":")),
        "map": json.dumps(file_map, separators=(",", ":")),
    }
    for key, (filename, content, content_type) in uploadables.items():
        files[key] = (filename, content, content_type)

    response = http.post_multipart(
        f"{_ORIGIN}{_GRAPHQL_PATH}",
        data=data,
        files=files,
        headers=_request_headers(
            credentials,
            lsd=lsd,
            friendly_name=friendly_name,
            referer=referer,
        ),
    )
    # post_multipart may return a parsed JSON dict; still enforce the same
    # GraphQL errors envelope as the non-resume JSON path (APL-05).
    if isinstance(response, dict):
        return _parse_graphql_payload(response)
    return _parse_graphql_json(str(response))


def _request_headers(
    credentials: dict[str, dict[str, str]] | None,
    *,
    lsd: str,
    friendly_name: str,
    referer: str | None,
) -> dict[str, str]:
    return request_headers(
        lsd=lsd,
        friendly_name=friendly_name,
        referer=referer or f"{_ORIGIN}/",
        credentials=credentials,
    )


def _parse_graphql_payload(data: object) -> dict[str, Any]:
    """Reject GraphQL error envelopes so resume and non-resume submits agree."""
    if not isinstance(data, dict):
        raise ValueError("meta_careers GraphQL returned unexpected payload")
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, str) and message.strip():
                raise ValueError(f"meta_careers GraphQL error: {message.strip()}")
        raise ValueError("meta_careers GraphQL returned errors")
    return data


def _parse_graphql_json(body: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("meta_careers GraphQL returned invalid JSON") from exc
    return _parse_graphql_payload(data)
