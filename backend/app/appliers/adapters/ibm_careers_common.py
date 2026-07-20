"""Shared helpers for the IBM Careers (Avature) apply adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

_JOB_ID_RE = re.compile(r"^\d+$")
_DEFAULT_CAREERS_BASE = "https://careers.ibm.com"
_AVATURE_HOST_SUFFIX = ".avature.net"
_IMPORT_PATH_MARKER = "/importservice/"


def resolve_job_id(config: dict[str, Any], job_external_id: str, job_url: str) -> str | None:
    """Numeric IBM / Avature job id from config, external id, or URL."""
    for raw in (config.get("job_id"), config.get("jobId"), job_external_id):
        candidate = str(raw or "").strip()
        if candidate and _JOB_ID_RE.fullmatch(candidate):
            return candidate
    if not job_url:
        return None
    parsed = urlparse(job_url)
    params = parse_qs(parsed.query)
    for key in ("jobId", "job_id", "jobid"):
        values = params.get(key) or []
        if values and _JOB_ID_RE.fullmatch(str(values[0]).strip()):
            return str(values[0]).strip()
    parts = [part for part in parsed.path.split("/") if part]
    # /careers/JobDetail/<slug>/<id> or …/JobDetail?jobId=<id>
    if parts and _JOB_ID_RE.fullmatch(parts[-1]):
        return parts[-1]
    return None


def resolve_careers_base_url(config: dict[str, Any], job_url: str) -> str:
    """Careers portal origin (IBM vanity or Avature host)."""
    base = str(config.get("careers_base_url") or "").strip().rstrip("/")
    if base:
        return base
    if job_url:
        parsed = urlparse(job_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            host = parsed.netloc.lower()
            if (
                host == "careers.ibm.com"
                or host.endswith(_AVATURE_HOST_SUFFIX)
                or host in {"www.ibm.com", "ibm.com"}
            ):
                return f"{parsed.scheme}://{parsed.netloc}"
    return _DEFAULT_CAREERS_BASE


def job_detail_url(careers_base: str, job_id: str) -> str:
    """Canonical JobDetail URL for the given portal origin."""
    return f"{careers_base.rstrip('/')}/careers/JobDetail?jobId={job_id}"


def application_methods_url(careers_base: str, job_id: str) -> str:
    """Avature apply entry page (login / register / resume methods)."""
    return f"{careers_base.rstrip('/')}/careers/ApplicationMethods?jobId={job_id}"


def resolve_import_url(
    config: dict[str, Any], credentials: dict[str, dict[str, str]] | None
) -> str | None:
    """Avature External Import Service endpoint from config or credential session."""
    session = (credentials or {}).get("session") or {}
    for source in (session, config):
        for key in (
            "avature_import_url",
            "import_url",
            "import_service_url",
            "avature_import_service_url",
        ):
            raw = source.get(key) if isinstance(source, dict) else None
            candidate = str(raw or "").strip()
            if candidate and _looks_like_import_url(candidate):
                return candidate.rstrip("/") + "/"
    return None


def resolve_api_key(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Optional X-Avature-Key for Import Service authentication."""
    session = (credentials or {}).get("session") or {}
    for source in (session, config):
        for key in ("api_key", "avature_api_key", "x_avature_key", "import_api_key"):
            raw = source.get(key) if isinstance(source, dict) else None
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return None


def extract_error_message(payload: object) -> str:
    """Best-effort error string from an Avature Import Service JSON body."""
    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip() and value.strip().lower() != "null":
                return value.strip()
        result = payload.get("result")
        if isinstance(result, str) and result.strip() and result.strip().lower() != "accepted":
            return result.strip()
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return "ibm_careers apply failed"


def extract_import_code(payload: object) -> str | None:
    """Import process id from a successful Import Service response."""
    if not isinstance(payload, dict):
        return None
    for key in ("importCode", "import_code", "importerProcessId"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _looks_like_import_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return _IMPORT_PATH_MARKER in parsed.path.lower()
