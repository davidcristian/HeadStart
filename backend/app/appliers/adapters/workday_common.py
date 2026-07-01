"""Shared Workday CXS HTTP helpers for the apply adapter.

Workday career sites expose a public Candidate Experience Service (CXS) API.
Job listings use POST ``/wday/cxs/{tenant}/{site}/jobs``; applications use
authenticated endpoints under ``/wday/cxs/{tenant}/jobpostings/...`` and
``/wday/cxs/{tenant}/jobapplication/...`` with session cookies and a CSRF token.
"""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.workday_payload import (
    build_application_payload,
    build_name_body,
    build_supplemental_text,
    render_cover_letter,
    split_name,
)
from app.appliers.adapters.workday_target import (
    WorkdayTarget,
    resolve_job_path,
    resolve_job_posting_id,
    resolve_target,
)
from app.scrapers.http import HttpClient

CSRF_HEADER = "X-CALYPSO-CSRF-TOKEN"
SESSION_HEADER = "X-Cxs-Session-Id"

__all__ = [
    "CSRF_HEADER",
    "SESSION_HEADER",
    "WorkdayTarget",
    "build_application_payload",
    "build_http_client",
    "build_name_body",
    "build_supplemental_text",
    "calypso_common_url",
    "calypso_jobapplication_url",
    "cxs_jobapplication_url",
    "fetch_job_posting_info",
    "job_posting_info_url",
    "render_cover_letter",
    "request_headers",
    "resolve_csrf_token",
    "resolve_job_path",
    "resolve_job_posting_id",
    "resolve_target",
    "split_name",
]


def resolve_csrf_token(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """CSRF token from credential session or cookies."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("csrf_token", "calypso_csrf_token", "CALYPSO_CSRF_TOKEN"):
            value = session.get(key)
            if value:
                return str(value)
        cookies = credentials.get("cookies") or {}
        cookie_token = cookies.get("CALYPSO_CSRF_TOKEN")
        if cookie_token:
            return str(cookie_token)
    config_token = config.get("csrf_token")
    return str(config_token) if config_token else None


def build_http_client(
    credentials: dict[str, dict[str, str]] | None,
    *,
    headers: dict[str, str] | None = None,
) -> HttpClient:
    """HttpClient that carries stored site cookies/headers for CXS calls."""
    cred_headers = (credentials or {}).get("headers") or {}
    cred_cookies = (credentials or {}).get("cookies") or {}
    merged_headers = {**cred_headers, **(headers or {})}
    return HttpClient(headers=merged_headers, cookies=cred_cookies)


def job_posting_info_url(target: WorkdayTarget, job_path: str) -> str:
    """CXS job detail URL used to read questionnaire metadata."""
    return f"https://{target.host}/wday/cxs/{target.tenant}/{target.site}/job/{job_path}"


def calypso_common_url(target: WorkdayTarget, suffix: str) -> str:
    """Calypso common-service URL (questionnaire definitions)."""
    return f"https://{target.host}/wday/calypso/cxs/common/{target.tenant}/{suffix}"


def calypso_jobapplication_url(target: WorkdayTarget, suffix: str) -> str:
    """Calypso jobapplication-service URL (questionnaire submit)."""
    return f"https://{target.host}/wday/calypso/cxs/jobapplication/{target.tenant}/{suffix}"


def cxs_jobapplication_url(target: WorkdayTarget, application_id: str, section: str) -> str:
    """Direct CXS application section URL (name, finalize, terms, ...)."""
    return f"{target.api_base()}/jobapplication/{application_id}/{section}"


def fetch_job_posting_info(
    http: HttpClient, target: WorkdayTarget, job_path: str
) -> dict[str, Any]:
    """Load job posting metadata (questionnaire ids, etc.) from CXS."""
    url = job_posting_info_url(target, job_path)
    headers = {
        "Accept": "application/json",
        "Accept-Language": target.locale,
        "Referer": target.job_page_url(job_path),
    }
    data = http.get_json(url, headers=headers)
    if not isinstance(data, dict):
        return {}
    posting = data.get("jobPostingInfo")
    return posting if isinstance(posting, dict) else {}


def request_headers(
    target: WorkdayTarget,
    job_path: str,
    *,
    csrf_token: str | None,
    session_id: str | None = None,
    form_definition: bool = False,
    credentials: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """Standard CXS headers for apply requests."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": target.locale,
        "Referer": target.apply_referer(job_path),
    }
    if csrf_token:
        headers[CSRF_HEADER] = csrf_token
    if session_id:
        headers[SESSION_HEADER] = session_id
    if form_definition:
        headers["form-definition"] = "true"
    if credentials:
        cred_headers = credentials.get("headers") or {}
        headers.update(cred_headers)
        cookie_header = _cookie_header(credentials.get("cookies") or {})
        if cookie_header:
            headers["Cookie"] = cookie_header
    return headers


def _cookie_header(cookies: dict[str, str]) -> str:
    """Serialize cookie dict for a single Cookie request header."""
    return "; ".join(f"{key}={value}" for key, value in cookies.items())
