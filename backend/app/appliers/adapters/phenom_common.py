"""Shared helpers for the Phenom People apply adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_DEFAULT_APPLY_API_BASE = "https://api.phenompro.com"
_DEFAULT_COUNTRY = "us"
_DEFAULT_LOCALE = "en_us"
_CSRF_RE = re.compile(r'"csrfToken"\s*:\s*"([^"]+)"')
_REF_NUM_RE = re.compile(r'"refNum"\s*:\s*"([^"]+)"')
_JOB_PATH_RE = re.compile(r"/job/([^/?#]+)", re.IGNORECASE)


def resolve_careers_base_url(config: dict[str, Any], job_url: str) -> str | None:
    """Phenom careers origin from config or a careers job / search URL."""
    base = str(config.get("careers_base_url") or "").strip().rstrip("/")
    if base:
        return base
    if not job_url.strip():
        return None
    try:
        origin, _, _ = _base_from_url(job_url.strip())
    except ValueError:
        return None
    return origin


def resolve_country(config: dict[str, Any], job_url: str) -> str:
    """Country path segment for Phenom pages (default ``us``)."""
    raw = str(config.get("country") or "").strip()
    if raw:
        return raw.lower()
    if job_url.strip():
        try:
            _, country, _ = _base_from_url(job_url.strip())
        except ValueError:
            country = ""
        if country:
            return country
    return _DEFAULT_COUNTRY


def resolve_locale(config: dict[str, Any], job_url: str) -> str:
    """Locale for Phenom widgets / Apply API headers (default ``en_us``)."""
    raw = str(config.get("locale") or "").strip()
    if raw:
        return raw
    if job_url.strip():
        try:
            _, _, locale = _base_from_url(job_url.strip())
        except ValueError:
            locale = ""
        if locale:
            return locale
    return _DEFAULT_LOCALE


def resolve_ref_num(config: dict[str, Any], credentials: dict[str, Any] | None) -> str:
    """Tenant ``refNum`` from config or credential session."""
    for source in (config, (credentials or {}).get("session") or {}):
        if not isinstance(source, dict):
            continue
        for key in ("ref_num", "refNum"):
            candidate = str(source.get(key) or "").strip()
            if candidate:
                return candidate
    return ""


def resolve_job_id(config: dict[str, Any], job_external_id: str, job_url: str) -> str | None:
    """Phenom ``jobSeqNo`` / job id from config, external id, or ``/job/<id>`` URL."""
    for raw in (
        config.get("job_seq_no"),
        config.get("jobSeqNo"),
        config.get("job_id"),
        config.get("jobId"),
        job_external_id,
    ):
        candidate = str(raw or "").strip()
        if candidate:
            return candidate
    if not job_url.strip():
        return None
    match = _JOB_PATH_RE.search(job_url)
    if match:
        return match.group(1).strip() or None
    return None


def search_results_url(careers_base: str, country: str, locale: str) -> str:
    """CSRF-seeding search-results page for a Phenom tenant."""
    lang = locale.split("_", 1)[0] or "en"
    return f"{careers_base.rstrip('/')}/{country}/{lang}/search-results"


def job_page_url(careers_base: str, country: str, locale: str, job_id: str) -> str:
    """Public job-details page URL for Referer headers."""
    lang = locale.split("_", 1)[0] or "en"
    return f"{careers_base.rstrip('/')}/{country}/{lang}/job/{job_id}"


def parse_session_html(html: str) -> tuple[str | None, str]:
    """Extract CSRF token and optional refNum from a careers HTML page."""
    csrf: str | None = None
    match = _CSRF_RE.search(html)
    if match:
        csrf = match.group(1)
    ref_match = _REF_NUM_RE.search(html)
    ref_num = ref_match.group(1).strip() if ref_match else ""
    return csrf, ref_num


def apply_api_base(config: dict[str, Any]) -> str:
    """Phenom partner Apply API origin (overrideable for fixtures / staging)."""
    raw = str(config.get("phenom_apply_api_base") or config.get("apply_api_base") or "").strip()
    if raw:
        return raw.rstrip("/")
    return _DEFAULT_APPLY_API_BASE


def applications_url(config: dict[str, Any]) -> str:
    """POST URL that creates an application via the partner Apply API."""
    return f"{apply_api_base(config)}/apply/v2/applications"


def resolve_access_token(credentials: dict[str, Any] | None, config: dict[str, Any]) -> str | None:
    """OAuth bearer token for the Phenom partner Apply API."""
    for source in (credentials or {}).get("session") or {}, config:
        if not isinstance(source, dict):
            continue
        for key in (
            "access_token",
            "phenom_access_token",
            "api_token",
            "bearer_token",
            "oauth_token",
        ):
            candidate = str(source.get(key) or "").strip()
            if candidate:
                return candidate
    return None


def resolve_external_apply_url(config: dict[str, Any]) -> str | None:
    """Optional apply URL override when jobDetail fetch is skipped."""
    for key in ("external_apply_url", "apply_url", "applyUrl"):
        candidate = str(config.get(key) or "").strip()
        if candidate:
            return candidate
    return None


def extract_error_message(data: object) -> str | None:
    """Pull a human-readable error from a Phenom Apply API JSON body."""
    if isinstance(data, str) and data.strip():
        return data.strip()
    if not isinstance(data, dict):
        return None
    for key in ("statusMessage", "message", "error", "errorMessage"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
        if isinstance(first, dict):
            for key in ("message", "errorMessage", "statusMessage"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def extract_application_id(data: object) -> str | None:
    """Best-effort application id from a successful Apply API response."""
    if not isinstance(data, dict):
        return None
    for key in ("applicationId", "id", "candidateId"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    inner = data.get("data")
    if isinstance(inner, dict):
        for key in ("applicationId", "id", "candidateId"):
            value = inner.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _base_from_url(query_url: str) -> tuple[str, str, str]:
    """Extract careers origin and optional country/locale from a careers URL."""
    parsed = urlparse(query_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("phenom apply job_url must be an http(s) careers site URL")
    base = f"{parsed.scheme}://{parsed.netloc.lower()}"
    parts = [part for part in parsed.path.split("/") if part]
    country = ""
    locale = ""
    if len(parts) >= 2 and parts[0] and parts[1]:
        country = parts[0].lower()
        lang = parts[1].lower()
        if "_" in lang:
            locale = lang
        elif country == "global":
            locale = f"{lang}_global"
        else:
            locale = f"{lang}_{country}"
    return base, country, locale
