"""GraphQL client helpers for Uber Careers apply."""

from __future__ import annotations

import json
from typing import Any

from app.appliers.adapters.uber_careers_common import api_headers, graphql_url
from app.scrapers.http import HttpClient

_SUBMIT_MUTATION = """
mutation submitApplication($applicationFormRequest: ApplicationFormRequestInput!) {
  submitApplication(applicationFormRequest: $applicationFormRequest)
}
""".strip()


def submit_application(
    http: HttpClient,
    *,
    application_form_request: dict[str, Any],
    referer: str,
) -> Any:
    """POST the careers apply submitApplication mutation."""
    body = http.post_json(
        graphql_url(),
        json={
            "operationName": "submitApplication",
            "query": _SUBMIT_MUTATION,
            "variables": {"applicationFormRequest": application_form_request},
        },
        headers=api_headers(referer=referer),
    )
    return _parse_graphql_response(body)


def _parse_graphql_response(body: Any) -> Any:
    if not isinstance(body, dict):
        raise ValueError("uber_careers GraphQL returned unexpected payload")
    errors = body.get("errors")
    if isinstance(errors, list) and errors:
        message = _first_error_message(errors)
        raise ValueError(f"uber_careers GraphQL error: {message}")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ValueError("uber_careers GraphQL returned no data")
    if "submitApplication" not in data:
        raise ValueError("uber_careers GraphQL response missing submitApplication")
    return data["submitApplication"]


def _first_error_message(errors: list[Any]) -> str:
    for item in errors:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if isinstance(message, str) and message.strip():
            trimmed = message.strip()
            if trimmed.startswith("{"):
                try:
                    parsed = json.loads(trimmed)
                except json.JSONDecodeError:
                    return trimmed
                if isinstance(parsed, dict):
                    nested = parsed.get("message")
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
            return trimmed
    return "unknown GraphQL error"
