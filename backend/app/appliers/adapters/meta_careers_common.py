"""Shared Meta Careers (metacareers.com) apply helpers."""

from __future__ import annotations

import re
from typing import Any

_ORIGIN = "https://www.metacareers.com"
_JOB_URL_RE = re.compile(
    r"(?:www\.)?(?:metacareers|facebookcareers)\.com/(?:jobs|profile/job_details|profile/create_application)/(\d+)",
    re.IGNORECASE,
)

JOB_DETAILS_QUERY = "CandidatePortalJobDetailsViewQuery"
JOB_DETAILS_DOC_ID = "27371134039243725"
SUBMIT_MUTATION = "CandidateChatbotApplicationDetailSubmitMutation"
SUBMIT_DOC_ID = "26338665575783815"
_DEFAULT_ASBD_ID = "359341"
_GRAPHQL_PATH = "/api/graphql/"


def resolve_requisition_id(config: dict[str, Any], job_url: str, job_external_id: str) -> str:
    """Numeric Meta requisition id from config, URL, or seen_job external_id."""
    configured = config.get("requisition_id") or config.get("job_id")
    if configured:
        return str(configured).strip()
    match = _JOB_URL_RE.search(job_url)
    if match:
        return match.group(1)
    external = str(job_external_id).strip()
    if external.isdigit():
        return external
    raise ValueError("meta_careers applier could not resolve requisition id")


def job_details_url(requisition_id: str) -> str:
    """Public job detail page used to bootstrap GraphQL anti-CSRF tokens."""
    return f"{_ORIGIN}/profile/job_details/{requisition_id}/"


def apply_url(requisition_id: str) -> str:
    """Candidate application flow entry point."""
    return f"{_ORIGIN}/profile/create_application/{requisition_id}/"


def public_job_url(requisition_id: str) -> str:
    """Canonical public posting URL."""
    return f"{_ORIGIN}/jobs/{requisition_id}/"


def resolve_session_id(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Browser session key required by Meta's create-application mutation."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("session_id", "session_key"):
            value = session.get(key)
            if value:
                return str(value)
    for key in ("session_id", "session_key"):
        value = config.get(key)
        if value:
            return str(value)
    return None


def has_session_cookies(credentials: dict[str, dict[str, str]] | None) -> bool:
    """True when credential cookies look like a logged-in Meta Careers session."""
    if not credentials:
        return False
    cookies = credentials.get("cookies") or {}
    if not cookies:
        return False
    names = {name.lower() for name in cookies}
    return bool(
        names.intersection(
            {
                "c_user",
                "xs",
                "datr",
                "sb",
            }
        )
    )


def graphql_headers(*, lsd: str, friendly_name: str) -> dict[str, str]:
    """Headers for Meta Careers Relay GraphQL requests."""
    return {
        "x-fb-friendly-name": friendly_name,
        "x-fb-lsd": lsd,
        "x-asbd-id": _DEFAULT_ASBD_ID,
    }


def request_headers(
    *,
    lsd: str,
    friendly_name: str,
    referer: str,
    credentials: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """Relay GraphQL headers with optional credential cookies."""
    headers = graphql_headers(lsd=lsd, friendly_name=friendly_name)
    headers["Referer"] = referer
    if credentials:
        cred_headers = credentials.get("headers") or {}
        headers.update({str(k): str(v) for k, v in cred_headers.items()})
        cookie_header = _cookie_header(credentials.get("cookies") or {})
        if cookie_header:
            headers["Cookie"] = cookie_header
    return headers


def _cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())


def extract_application_id(response: dict[str, Any]) -> str | None:
    """Return the application id from a create-application mutation response."""
    payload = response.get("data", {}).get("xcp_create_application_v2")
    if not isinstance(payload, dict):
        return None
    app_id = payload.get("application_id")
    if app_id is not None:
        return str(app_id)
    consideration = payload.get("consideration")
    if isinstance(consideration, dict) and consideration.get("id") is not None:
        return str(consideration["id"])
    return None
