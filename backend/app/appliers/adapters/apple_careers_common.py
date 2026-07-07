"""Shared Apple Careers (jobs.apple.com) apply HTTP helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

ORIGIN = "https://jobs.apple.com"
API_BASE = f"{ORIGIN}/api/v1/js"
DEFAULT_LOCALE = "en-us"
CSRF_HEADER = "X-Apple-CSRF-Token"
TRIGGER_SELF_SUBMIT = "TALENT_SELF_SUBMIT"
_DETAILS_PATH_RE = re.compile(
    r"/([a-z]{2}-[a-z]{2})/details/([^/]+)/([^/?#]+)",
    re.IGNORECASE,
)


def resolve_locale(config: dict[str, Any]) -> str:
    """Path locale for jobs.apple.com URLs."""
    locale = config.get("locale") or config.get("hl")
    return str(locale).strip().lower() if locale else DEFAULT_LOCALE


def resolve_job_detail_url(
    config: dict[str, Any],
    job_url: str,
    job_external_id: str,
) -> str | None:
    """Best-effort public job detail URL for hydration parsing."""
    if job_url.strip():
        return job_url.strip()
    configured = config.get("job_detail_url") or config.get("detail_url")
    if configured:
        return str(configured).strip()
    slug = str(config.get("transformed_posting_title") or config.get("slug") or "").strip()
    req_id = str(config.get("req_id") or config.get("position_id") or job_external_id).strip()
    if not req_id:
        return None
    locale = resolve_locale(config)
    if slug:
        params = urlencode({"team": config["team"]}) if config.get("team") else ""
        suffix = f"?{params}" if params else ""
        return f"{ORIGIN}/{locale}/details/{req_id}/{slug}{suffix}"
    return f"{ORIGIN}/{locale}/details/{req_id}"


def apply_page_url(locale: str, position_id: str) -> str:
    """Authenticated apply route surfaced in the Apple Careers UI."""
    return f"{ORIGIN}/app/{locale}/apply/{position_id}"


def csrf_token_url() -> str:
    return f"{API_BASE}/CSRFToken"


def questionnaire_url(job_id: str) -> str:
    return f"{API_BASE}/jobDetails/{job_id}/questionnaire"


def apply_job_url(talent_id: str) -> str:
    return f"{API_BASE}/talent/{talent_id}/applyJob"


def upload_resume_url(talent_id: str) -> str:
    return f"{API_BASE}/talent/{talent_id}/file/uploadFile"


def resolve_talent_id(
    credentials: dict[str, dict[str, str]] | None,
    config: dict[str, Any],
) -> str | None:
    """Apple talent id from credential session or source/search config."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("talent_id", "talentId", "talentID"):
            value = session.get(key)
            if value:
                return str(value).strip()
    for key in ("talent_id", "talentId", "talentID"):
        value = config.get(key)
        if value:
            return str(value).strip()
    return None


def resolve_csrf_token(
    credentials: dict[str, dict[str, str]] | None,
    config: dict[str, Any],
) -> str | None:
    """CSRF token from credential session/config."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("csrf_token", "csrf", "apple_csrf_token"):
            value = session.get(key)
            if value:
                return str(value).strip()
        headers = credentials.get("headers") or {}
        header_value = headers.get(CSRF_HEADER)
        if header_value:
            return str(header_value).strip()
    for key in ("csrf_token", "csrf", "apple_csrf_token"):
        value = config.get(key)
        if value:
            return str(value).strip()
    return None


def has_session_cookies(credentials: dict[str, dict[str, str]] | None) -> bool:
    """True when credential cookies look like a logged-in Apple Careers session."""
    if not credentials:
        return False
    cookies = credentials.get("cookies") or {}
    if not cookies:
        return False
    names = {name.lower() for name in cookies}
    known = {"myacinfo", "dawsp", "dslang", "site", "aasp"}
    return bool(names.intersection(known)) or len(cookies) >= 2


def request_headers(
    *,
    csrf_token: str,
    referer: str,
    credentials: dict[str, dict[str, str]] | None = None,
    json_body: bool = True,
) -> dict[str, str]:
    """Standard Apple Careers AJAX headers."""
    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        CSRF_HEADER: csrf_token,
        "Referer": referer,
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    if credentials:
        cred_headers = credentials.get("headers") or {}
        headers.update(cred_headers)
        cookie_header = _cookie_header(credentials.get("cookies") or {})
        if cookie_header:
            headers["Cookie"] = cookie_header
    return headers


def unwrap_response(response: Any) -> Any:
    """Return Apple Careers API data payloads wrapped in {success, data}."""
    if isinstance(response, dict) and response.get("success") is True:
        return response.get("data")
    if isinstance(response, dict) and "data" in response:
        return response.get("data")
    return response


def apply_error_message(response: Any) -> str | None:
    """Human-readable message when an applyJob JSON body reports failure."""
    if not isinstance(response, dict):
        return None
    if response.get("success") is False:
        errors = response.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                message = first.get("message") or first.get("error")
                if message:
                    return str(message)
        for key in ("message", "error"):
            value = response.get(key)
            if value and str(value).strip():
                return str(value)
        return "apple_careers apply request failed"
    # Bare error envelopes (no success:false) — same fallthrough as Microsoft.
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            message = first.get("message") or first.get("error")
            if message:
                return str(message)
    error = response.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if message and str(message).strip():
            return str(message)
    if error and not isinstance(error, (dict, list)) and str(error).strip():
        return str(error)
    return None


def extract_application_id(response: Any) -> str | None:
    """Best-effort application id from an applyJob response payload."""
    data = unwrap_response(response)
    if not isinstance(data, dict):
        return None
    for key in ("applicationId", "application_id", "id", "connectionId", "connection_id"):
        value = data.get(key)
        if value is not None:
            return str(value)
    roles = data.get("roles")
    if isinstance(roles, dict):
        for key in ("applicationId", "connectionId", "id"):
            value = roles.get(key)
            if value is not None:
                return str(value)
    return None


def parse_details_path(job_url: str) -> tuple[str, str, str] | None:
    """Return (locale, req_id, slug) from a /details/ URL."""
    match = _DETAILS_PATH_RE.search(job_url)
    if not match:
        return None
    return match.group(1).lower(), match.group(2), match.group(3)


def _cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())
