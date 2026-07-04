"""Shared Microsoft Careers (Eightfold SmartApply) HTTP helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from app.scrapers.http import HttpClient

ORIGIN = "https://apply.careers.microsoft.com"
DEFAULT_DOMAIN = "microsoft.com"
DEFAULT_LOCALE = "en"
CSRF_HEADER = "X-CSRF-Token"
_CSRF_META_RE = re.compile(r'name="_csrf"\s+content="([^"]+)"', re.IGNORECASE)
_JOB_URL_RE = re.compile(r"/careers/job/(\d+)", re.IGNORECASE)


def resolve_domain(config: dict[str, Any]) -> str:
    """Eightfold domain slug from source/search config."""
    domain = config.get("domain")
    return str(domain).strip() if domain else DEFAULT_DOMAIN


def resolve_position_id(config: dict[str, Any], job_url: str, job_external_id: str) -> str:
    """Numeric Eightfold position id from config, URL, or seen_job external_id."""
    configured = config.get("position_id") or config.get("job_id")
    if configured:
        return str(configured).strip()
    match = _JOB_URL_RE.search(job_url)
    if match:
        return match.group(1)
    return str(job_external_id).strip()


def apply_page_url(position_id: str) -> str:
    """Candidate apply page used for CSRF and Referer headers."""
    return f"{ORIGIN}/careers/apply/{position_id}"


def job_detail_url(domain: str, position_id: str, *, locale: str = DEFAULT_LOCALE) -> str:
    """Public SmartApply job detail endpoint."""
    params = urlencode({"domain": domain, "hl": locale})
    return f"{ORIGIN}/api/apply/v2/jobs/{position_id}?{params}"


def questions_url(domain: str, position_id: str, *, locale: str = DEFAULT_LOCALE) -> str:
    """Application questionnaire metadata for a position."""
    params = urlencode({"domain": domain, "position_id": position_id, "hl": locale})
    return f"{ORIGIN}/api/apply/v2/questions?{params}"


def candidate_url(domain: str, position_id: str, *, locale: str = DEFAULT_LOCALE) -> str:
    """Candidate profile endpoint for a specific apply session."""
    params = urlencode({"domain": domain, "position_id": position_id, "hl": locale})
    return f"{ORIGIN}/api/apply/v2/candidate?{params}"


def submit_url(domain: str, position_id: str) -> str:
    """Final application submit endpoint."""
    params = urlencode({"domain": domain, "position_id": position_id})
    return f"{ORIGIN}/api/application/v2/submit?{params}"


def upload_resume_url() -> str:
    """Resume upload endpoint (base64 JSON body)."""
    return f"{ORIGIN}/api/pcsx/upload_resume"


def resolve_csrf_token(
    credentials: dict[str, dict[str, str]] | None,
    config: dict[str, Any],
    *,
    http: HttpClient,
    apply_url: str,
) -> str | None:
    """CSRF token from credential session/config or the apply page meta tag."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("csrf_token", "_csrf", "csrf"):
            value = session.get(key)
            if value:
                return str(value)
    for key in ("csrf_token", "_csrf", "csrf"):
        value = config.get(key)
        if value:
            return str(value)
    try:
        html = http.get_text(apply_url)
    except Exception:
        return None
    match = _CSRF_META_RE.search(html)
    return match.group(1) if match else None


def build_http_client(
    credentials: dict[str, dict[str, str]] | None,
    *,
    headers: dict[str, str] | None = None,
) -> HttpClient:
    """HttpClient that carries stored site cookies/headers for SmartApply calls."""
    cred_headers = (credentials or {}).get("headers") or {}
    cred_cookies = (credentials or {}).get("cookies") or {}
    merged_headers = {**cred_headers, **(headers or {})}
    return HttpClient(headers=merged_headers, cookies=cred_cookies)


def request_headers(
    *,
    csrf_token: str,
    referer: str,
    credentials: dict[str, dict[str, str]] | None = None,
    json_body: bool = True,
) -> dict[str, str]:
    """Standard SmartApply AJAX headers."""
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


def has_session_cookies(credentials: dict[str, dict[str, str]] | None) -> bool:
    """True when credential cookies look like a logged-in Microsoft Careers session."""
    if not credentials:
        return False
    cookies = credentials.get("cookies") or {}
    if not cookies:
        return False
    names = {name.lower() for name in cookies}
    known = {"_vs", "_vscid", "session", "connect.sid"}
    return bool(names.intersection(known)) or len(cookies) >= 2


def _cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())


def api_error_message(response: Any) -> str | None:
    """Human-readable message when a SmartApply JSON body reports errors."""
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
        return "microsoft_careers apply request failed"
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
    return None


def extract_application_id(response: Any) -> str | None:
    """Best-effort application id from a submit response payload."""
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        for key in ("application_id", "applicationId", "id", "profile_application_id"):
            value = data.get(key)
            if value is not None:
                return str(value)
    for key in ("application_id", "applicationId", "id"):
        value = response.get(key)
        if value is not None:
            return str(value)
    return None
