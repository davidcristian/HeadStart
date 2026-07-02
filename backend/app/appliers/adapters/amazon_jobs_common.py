"""Shared Amazon Jobs (amazon.jobs) apply HTTP helpers."""

from __future__ import annotations

import re
from typing import Any

ORIGIN = "https://www.amazon.jobs"
ACCOUNT_ORIGIN = "https://account.amazon.jobs"
DEFAULT_LOCALE = "en"
_JOB_PATH_RE = re.compile(r"/jobs/(\d+)(?:/|$)", re.IGNORECASE)


def resolve_locale(config: dict[str, Any]) -> str:
    """Path locale for public search and apply URLs."""
    locale = config.get("locale") or config.get("hl")
    return str(locale).strip() if locale else DEFAULT_LOCALE


def resolve_job_id(config: dict[str, Any], job_url: str, job_external_id: str) -> str:
    """iCIMS numeric job id from config, URL, or seen_job external_id."""
    configured = config.get("job_id") or config.get("id_icims") or config.get("position_id")
    if configured:
        return str(configured).strip()
    match = _JOB_PATH_RE.search(job_url)
    if match:
        return match.group(1)
    return str(job_external_id).strip()


def apply_page_url(job_id: str) -> str:
    """Candidate apply page used for Referer headers."""
    return f"{ORIGIN}/applicant/jobs/{job_id}/apply"


def account_apply_url(job_id: str) -> str:
    """Account portal apply URL surfaced in search results."""
    return f"{ACCOUNT_ORIGIN}/jobs/{job_id}/apply"


def job_search_url(locale: str, job_id: str) -> str:
    """Public search.json lookup for a single posting by iCIMS id."""
    return f"{ORIGIN}/{locale}/search.json?result_limit=1&base_query={job_id}"


def applicant_show_url() -> str:
    return f"{ORIGIN}/api/apply/applicant"


def applicant_update_url() -> str:
    return f"{ORIGIN}/api/apply/applicant/"


def documents_url() -> str:
    return f"{ORIGIN}/api/apply/documents"


def draft_application_url(job_id: str) -> str:
    return f"{ORIGIN}/api/apply/jobs/{job_id}/application/draft_application"


def submit_application_url(job_id: str) -> str:
    return f"{ORIGIN}/api/apply/jobs/{job_id}/application/submit_application"


def get_application_url(job_id: str) -> str:
    return f"{ORIGIN}/api/apply/jobs/{job_id}/application/get_application"


def job_details_url(job_id: str) -> str:
    return f"{ORIGIN}/api/apply/jobs/{job_id}/details"


def request_headers(
    *,
    referer: str,
    credentials: dict[str, dict[str, str]] | None = None,
    json_body: bool = True,
) -> dict[str, str]:
    """Standard amazon.jobs applicant AJAX headers."""
    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
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


def _cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())


def has_session_cookies(credentials: dict[str, dict[str, str]] | None) -> bool:
    """True when credential cookies look like a logged-in amazon.jobs session."""
    if not credentials:
        return False
    cookies = credentials.get("cookies") or {}
    if not cookies:
        return False
    names = {name.lower() for name in cookies}
    known = {"__host-mons-sid", "mons-sid", "session", "sessionid", "awscid"}
    return bool(names.intersection(known)) or len(cookies) >= 2


def api_error_message(response: Any) -> str | None:
    """Human-readable message when an amazon.jobs JSON body reports errors."""
    if not isinstance(response, dict):
        return None
    errors = response.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0]
    if isinstance(first, dict):
        message = first.get("message") or first.get("error")
        if message:
            return str(message)
    return "amazon_jobs apply request failed"


def extract_application_id(response: Any) -> str | None:
    """Best-effort application id from submit or get_application responses."""
    if not isinstance(response, dict):
        return None
    for key in ("application_id", "applicationId", "id", "disposition_id"):
        value = response.get(key)
        if value is not None:
            return str(value)
    data = response.get("data")
    if isinstance(data, dict):
        for key in ("application_id", "applicationId", "id", "disposition_id"):
            value = data.get(key)
            if value is not None:
                return str(value)
    application = response.get("application")
    if isinstance(application, dict):
        for key in ("id", "application_id", "applicationId"):
            value = application.get(key)
            if value is not None:
                return str(value)
    return None
