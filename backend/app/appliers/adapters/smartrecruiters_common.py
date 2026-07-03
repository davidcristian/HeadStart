"""Shared SmartRecruiters Application API helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.scrapers.http import HttpClient

SMARTRECRUITERS_API = "https://api.smartrecruiters.com"
POSTING_DETAIL_URL = (
    "https://api.smartrecruiters.com/v1/companies/{company_id}/postings/{posting_id}"
)
CONFIGURATION_URL = f"{SMARTRECRUITERS_API}/postings/{{posting_uuid}}/configuration"
APPLY_URL = f"{SMARTRECRUITERS_API}/postings/{{posting_uuid}}/candidates"

_SR_JOB_URL_RE = re.compile(
    r"jobs\.smartrecruiters\.com/([^/]+)/(\d+)",
    re.IGNORECASE,
)
_SR_CAREERS_URL_RE = re.compile(
    r"(?:careers|jobs)\.smartrecruiters\.com/([^/?#]+)",
    re.IGNORECASE,
)


def resolve_company_id(config: dict[str, Any], job_url: str) -> str | None:
    """Company slug from source config or a standard careers URL."""
    company_id = config.get("company_id") or config.get("site")
    if company_id:
        return str(company_id)
    match = _SR_JOB_URL_RE.search(job_url)
    if match:
        return match.group(1)
    match = _SR_CAREERS_URL_RE.search(job_url)
    return match.group(1) if match else None


def resolve_posting_uuid(
    config: dict[str, Any],
    posting_id: str,
    *,
    company_id: str | None,
    http: HttpClient,
) -> str:
    """Posting UUID from config or the public Postings detail API."""
    configured = config.get("posting_uuid")
    if configured:
        return str(configured)
    if not company_id:
        raise ValueError(
            "smartrecruiters applier needs config.company_id or a jobs.smartrecruiters.com URL"
        )
    url = POSTING_DETAIL_URL.format(company_id=company_id, posting_id=posting_id)
    data = http.get_json(url)
    if not isinstance(data, dict):
        raise ValueError("smartrecruiters posting detail returned unexpected payload")
    posting_uuid = data.get("uuid")
    if not posting_uuid:
        raise ValueError("smartrecruiters posting detail missing uuid")
    return str(posting_uuid)


def resolve_smart_token(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Application API token from credential session or source config."""
    if credentials:
        session_token = (credentials.get("session") or {}).get("smart_token")
        if session_token:
            return str(session_token)
    config_token = config.get("smart_token")
    return str(config_token) if config_token else None


def resolve_access_token(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """OAuth bearer token from credential session or source config."""
    if credentials:
        session_token = (credentials.get("session") or {}).get("access_token")
        if session_token:
            return str(session_token)
    config_token = config.get("access_token")
    return str(config_token) if config_token else None


def auth_headers(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> dict[str, str]:
    """SmartRecruiters Application API auth headers when credentials are present."""
    smart_token = resolve_smart_token(credentials, config)
    if smart_token:
        return {"X-SmartToken": smart_token}
    access_token = resolve_access_token(credentials, config)
    if access_token:
        return {"Authorization": f"Bearer {access_token}"}
    return {}


def split_name(full_name: str) -> tuple[str, str]:
    """Split a display name into SmartRecruiters first/last fields."""
    cleaned = full_name.strip()
    if not cleaned:
        return "", ""
    parts = cleaned.split(None, 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else parts[0]
    return first, last


def parse_company_from_url(job_url: str) -> str | None:
    """Best-effort company slug parse for error messages."""
    parsed = urlparse(job_url)
    host = parsed.netloc.lower()
    if host not in {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0] if parts else None
