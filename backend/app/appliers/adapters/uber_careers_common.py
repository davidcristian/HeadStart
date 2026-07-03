"""Shared helpers for the Uber Careers apply adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_ORIGIN = "https://www.uber.com"
_GRAPHQL_PATH = "/careers/apply/graphql"
_API_PATH = "/careers/apply/api"
_DEFAULT_LOCALE = "en"
_SOURCE_ORIGIN = "Uber Careers - New FE 2023 - Sign In"
_POSTING_TYPE_EXTERNAL = "POSTING_TYPE_EXTERNAL"
_JOB_ID_RE = re.compile(r"/(?:careers/list|careers/apply/form)/(\d+)")
_HOST_RE = re.compile(r"^(?:www\.)?uber\.com$", re.IGNORECASE)


def graphql_url() -> str:
    """Uber Careers Fusion GraphQL endpoint."""
    return f"{_ORIGIN}{_GRAPHQL_PATH}"


def api_url(handler: str, *, locale: str = _DEFAULT_LOCALE) -> str:
    """RPC-style careers apply API URL."""
    return f"{_ORIGIN}{_API_PATH}/{handler}?localeCode={locale}"


def apply_form_url(job_id: int, *, locale_path: str = "us/en") -> str:
    """Canonical apply-form page URL used as Referer."""
    return f"{_ORIGIN}/{locale_path.strip('/')}/careers/apply/form/{job_id}"


def resolve_locale(config: dict[str, Any]) -> str:
    """API locale code (default ``en``)."""
    return str(config.get("locale") or _DEFAULT_LOCALE)


def resolve_careers_locale_path(config: dict[str, Any]) -> str:
    """Careers path prefix for job/apply URLs."""
    return str(config.get("careers_locale_path") or "us/en").strip("/")


def resolve_job_id(
    config: dict[str, Any],
    job_url: str,
    job_external_id: str,
) -> int | None:
    """Resolve the numeric Uber job id from config, URL, or external id."""
    for key in ("job_id", "jobID"):
        raw = config.get(key)
        if raw is not None and str(raw).strip().isdigit():
            return int(str(raw).strip())
    for candidate in (job_external_id, job_url):
        if not candidate:
            continue
        if str(candidate).strip().isdigit():
            return int(str(candidate).strip())
        match = _JOB_ID_RE.search(candidate)
        if match:
            return int(match.group(1))
    return None


def resolve_session_token(
    credentials: dict[str, dict[str, str]] | None,
    config: dict[str, Any],
) -> str | None:
    """Logged-in Uber Careers session token from credentials or config."""
    for source in (
        (credentials or {}).get("session") or {},
        config,
    ):
        for key in ("session_token", "sessionToken"):
            value = source.get(key)
            if value and str(value).strip():
                return str(value).strip()
    return None


def api_headers(*, referer: str) -> dict[str, str]:
    """Headers shared by Uber careers apply REST and GraphQL calls."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": referer,
        "Origin": _ORIGIN,
        "x-csrf-token": "x",
        "x-uber-sites-page-edge-cache-enabled": "true",
    }


def yes_no_answer(answers: dict[str, str], key: str, *, default: str = "No") -> str:
    """Normalize a profile answer to Uber's Yes/No strings."""
    raw = str(answers.get(key) or default).strip().lower()
    if raw in {"yes", "y", "true", "1"}:
        return "Yes"
    if raw in {"no", "n", "false", "0"}:
        return "No"
    return str(answers.get(key) or default).strip() or default


def is_uber_host(job_url: str) -> bool:
    """Return whether a URL points at uber.com."""
    host = urlparse(job_url).netloc.lower()
    return bool(host and _HOST_RE.match(host))
