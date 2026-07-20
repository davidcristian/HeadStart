"""Shared helpers for the iCIMS Talent Cloud Partner API apply adapter."""

from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import urlparse

_API_HOST = "api.icims.com"
_JOB_ID_RE = re.compile(r"^\d+$")
_CUSTOMER_ID_RE = re.compile(r"^\d+$")
_LOCATION_ID_RE = re.compile(r"/(\d+)/?$")


def api_base() -> str:
    """iCIMS Talent Cloud API origin."""
    return f"https://{_API_HOST}"


def people_url(customer_id: str) -> str:
    """POST URL that creates a Person (candidate) profile."""
    return f"{api_base()}/customers/{customer_id}/people"


def applicant_workflows_url(customer_id: str) -> str:
    """POST URL that links a person to a job as an applicant workflow."""
    return f"{api_base()}/customers/{customer_id}/applicantworkflows"


def resolve_careers_base_url(config: dict[str, Any], job_url: str) -> str | None:
    """Careers site origin from config or a Jibe Attract / vanity job URL."""
    base = str(config.get("careers_base_url") or "").strip().rstrip("/")
    if base:
        return base
    if not job_url:
        return None
    parsed = urlparse(job_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    # Classic *.icims.com apply/login hosts are not the Jibe careers origin.
    if host.endswith(".icims.com"):
        return None
    return f"{parsed.scheme}://{host}"


def resolve_job_id(config: dict[str, Any], job_external_id: str, job_url: str) -> str | None:
    """Numeric iCIMS job / req id from config, external id, or URL path."""
    for raw in (config.get("job_id"), config.get("req_id"), job_external_id):
        candidate = str(raw or "").strip()
        if candidate and _JOB_ID_RE.fullmatch(candidate):
            return candidate
    if not job_url:
        return None
    parsed = urlparse(job_url)
    parts = [part for part in parsed.path.split("/") if part]
    if "jobs" in parts:
        idx = parts.index("jobs")
        if idx + 1 < len(parts) and _JOB_ID_RE.fullmatch(parts[idx + 1]):
            return parts[idx + 1]
    return None


def resolve_customer_id(
    config: dict[str, Any],
    credentials: dict[str, dict[str, str]] | None,
    job_detail: dict[str, Any] | None = None,
) -> str | None:
    """Customer (tenant) id from config, credential session, or job meta_data."""
    for source in (credentials or {}).get("session") or {}, config:
        for key in ("customer_id", "tenant_id", "icims_customer_id"):
            raw = source.get(key) if isinstance(source, dict) else None
            candidate = str(raw or "").strip()
            if candidate and _CUSTOMER_ID_RE.fullmatch(candidate):
                return candidate
    if job_detail is None:
        return None
    return customer_id_from_job_detail(job_detail)


def customer_id_from_job_detail(job_detail: dict[str, Any]) -> str | None:
    """Pull tenantId from Jibe Attract job ``meta_data.icims`` when present."""
    meta = job_detail.get("meta_data")
    if not isinstance(meta, dict):
        return None
    icims = meta.get("icims")
    if not isinstance(icims, dict):
        return None
    site = icims.get("primary_posted_site_object")
    if isinstance(site, dict):
        for key in ("tenantId", "tenant_id", "customerId", "customer_id"):
            candidate = str(site.get(key) or "").strip()
            if candidate and _CUSTOMER_ID_RE.fullmatch(candidate):
                return candidate
    for key in ("tenantId", "tenant_id", "customerId", "customer_id"):
        candidate = str(icims.get(key) or "").strip()
        if candidate and _CUSTOMER_ID_RE.fullmatch(candidate):
            return candidate
    return None


def resolve_basic_auth(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> tuple[str, str] | None:
    """Partner API username/password from credential session or source config."""
    session = (credentials or {}).get("session") or {}
    username = _first_str(
        session,
        "username",
        "basic_auth_username",
        "api_username",
        "icims_username",
    )
    password = _first_str(
        session,
        "password",
        "basic_auth_password",
        "api_password",
        "icims_password",
    )
    if username and password:
        return username, password
    username = _first_str(
        config,
        "username",
        "basic_auth_username",
        "api_username",
        "icims_username",
    )
    password = _first_str(
        config,
        "password",
        "basic_auth_password",
        "api_password",
        "icims_password",
    )
    if username and password:
        return username, password
    return None


def basic_auth_header(username: str, password: str) -> str:
    """HTTP Basic Authorization value for the Talent Cloud Partner API."""
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def parse_created_id(location: str | None) -> str | None:
    """Extract the numeric profile/workflow id from a ``Location`` response header."""
    if not location:
        return None
    match = _LOCATION_ID_RE.search(location.strip())
    return match.group(1) if match else None


def extract_error_message(payload: object) -> str:
    """Best-effort error string from an iCIMS JSON error body."""
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                message = first.get("errorMessage") or first.get("message")
                if message:
                    return str(message)
            if isinstance(first, str) and first.strip():
                return first.strip()
        for key in ("errorMessage", "message", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return "icims apply failed"


def _first_str(source: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw = source.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None
