"""Shared helpers for the SuccessFactors OData Recruiting apply adapter."""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

_JOB_ID_RE = re.compile(r"^\d+$")
_CLOUD_HOST_SUFFIX = ".jobs.hr.cloud.sap"
_DEFAULT_LOCALE = "en_US"
_DEFAULT_COUNTRY = "United States"


def resolve_job_id(config: dict[str, Any], job_external_id: str, job_url: str) -> str | None:
    """Numeric CSB / RCM job requisition id from config, external id, or job URL."""
    for raw in (
        config.get("job_req_id"),
        config.get("jobReqId"),
        config.get("job_id"),
        config.get("jobId"),
        job_external_id,
    ):
        candidate = str(raw or "").strip()
        if candidate and _JOB_ID_RE.fullmatch(candidate):
            return candidate
    if not job_url:
        return None
    parsed = urlparse(job_url)
    parts = [part for part in parsed.path.split("/") if part]
    # /job/<urlTitle>/<id>-en_US/ or /talentcommunity/apply/<id>/
    for idx, part in enumerate(parts):
        if part in {"apply", "job"} and idx + 1 < len(parts):
            token = parts[idx + 1]
            # Prefer the next segment when path is /job/<title>/<id>-locale/
            if part == "job" and idx + 2 < len(parts):
                token = parts[idx + 2]
            digits = token.split("-", 1)[0]
            if _JOB_ID_RE.fullmatch(digits):
                return digits
    if parts and _JOB_ID_RE.fullmatch(parts[-1].split("-", 1)[0]):
        return parts[-1].split("-", 1)[0]
    return None


def resolve_careers_base_url(config: dict[str, Any], job_url: str) -> str | None:
    """Career Site Builder origin from config or a ``*.jobs.hr.cloud.sap`` job URL."""
    base = str(config.get("careers_base_url") or "").strip().rstrip("/")
    if base:
        return base
    if not job_url:
        return None
    parsed = urlparse(job_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    if host.endswith(_CLOUD_HOST_SUFFIX) or host == "jobs.hr.cloud.sap":
        return f"{parsed.scheme}://{host}"
    return None


def resolve_locale(config: dict[str, Any]) -> str:
    """Apply URL / OData locale (default ``en_US``)."""
    locale = str(config.get("locale") or _DEFAULT_LOCALE).strip()
    return locale or _DEFAULT_LOCALE


def resolve_country(config: dict[str, Any], profile_answers: dict[str, Any]) -> str:
    """Candidate country required by OData ``Candidate`` create."""
    for source in (config, profile_answers):
        for key in ("country", "sf_country", "candidate_country"):
            raw = source.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return _DEFAULT_COUNTRY


def resolve_odata_base_url(
    config: dict[str, Any], credentials: dict[str, dict[str, str]] | None
) -> str | None:
    """SuccessFactors API host (``https://apiN.successfactors.com``) for OData."""
    session = (credentials or {}).get("session") or {}
    for source in (session, config):
        for key in (
            "odata_base_url",
            "api_base_url",
            "sf_api_base_url",
            "successfactors_api_base",
        ):
            raw = source.get(key) if isinstance(source, dict) else None
            candidate = str(raw or "").strip().rstrip("/")
            if candidate and _looks_like_odata_base(candidate):
                return candidate
    return None


def resolve_company_id(
    config: dict[str, Any], credentials: dict[str, dict[str, str]] | None
) -> str | None:
    """SF company id used in Basic Auth ``user@CompanyId`` (and optional query)."""
    session = (credentials or {}).get("session") or {}
    for source in (session, config):
        for key in ("company_id", "sf_company_id", "companyId", "tenant_id"):
            raw = source.get(key) if isinstance(source, dict) else None
            candidate = str(raw or "").strip()
            if candidate:
                return candidate
    return None


def resolve_basic_auth(
    credentials: dict[str, dict[str, str]] | None,
    config: dict[str, Any],
    *,
    company_id: str | None,
) -> tuple[str, str] | None:
    """API user credentials; username may already include ``@CompanyId``."""
    session = (credentials or {}).get("session") or {}
    username = _first_str(
        session,
        "username",
        "basic_auth_username",
        "api_username",
        "sf_username",
        "odata_username",
    )
    password = _first_str(
        session,
        "password",
        "basic_auth_password",
        "api_password",
        "sf_password",
        "odata_password",
    )
    if not username or not password:
        username = _first_str(
            config,
            "username",
            "basic_auth_username",
            "api_username",
            "sf_username",
            "odata_username",
        )
        password = _first_str(
            config,
            "password",
            "basic_auth_password",
            "api_password",
            "sf_password",
            "odata_password",
        )
    if not username or not password:
        return None
    if company_id and "@" not in username:
        username = f"{username}@{company_id}"
    return username, password


def basic_auth_header(username: str, password: str) -> str:
    """HTTP Basic Authorization value for OData."""
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def talentcommunity_apply_url(careers_base: str, job_id: str, locale: str) -> str:
    """Public CSB apply entry (login-gated Talent Community wizard)."""
    return f"{careers_base.rstrip('/')}/talentcommunity/apply/{job_id}/?locale={locale}"


def candidate_url(odata_base: str) -> str:
    """POST URL that creates a Recruiting ``Candidate``."""
    return f"{odata_base.rstrip('/')}/odata/v2/Candidate"


def job_application_url(odata_base: str) -> str:
    """POST URL that creates a ``JobApplication``."""
    return f"{odata_base.rstrip('/')}/odata/v2/JobApplication"


def attachment_url(odata_base: str) -> str:
    """POST URL that uploads an ``Attachment`` (resume)."""
    return f"{odata_base.rstrip('/')}/odata/v2/Attachment"


def extract_entity_id(payload: object, *keys: str) -> str | None:
    """Pull a created entity id from an OData ``d`` envelope or flat JSON."""
    if not isinstance(payload, dict):
        return None
    nested = payload.get("d")
    data = nested if isinstance(nested, dict) else payload
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def extract_error_message(payload: object) -> str:
    """Best-effort error string from an OData / SF JSON error body."""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, dict):
                value = message.get("value")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            if isinstance(message, str) and message.strip():
                return message.strip()
        for key in ("message", "errorMessage", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return "successfactors apply failed"


def json_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize a JSON body for ``HttpClient.post_raw``."""
    return json.dumps(payload).encode("utf-8")


def response_json(response: httpx.Response) -> object:
    """Parse an OData response body; fall back to truncated text."""
    try:
        return response.json()
    except (ValueError, TypeError):
        text = response.text
        return text[:2000] if text else {}


def odata_reports_error(body: object) -> bool:
    """True when the body is an OData error envelope."""
    return bool(isinstance(body, dict) and "error" in body)


def http_error_message(exc: httpx.HTTPError) -> str:
    """Prefer OData error JSON from an ``HTTPStatusError`` response body."""
    response = getattr(exc, "response", None)
    if response is None:
        return str(exc)
    try:
        response.read()
        return extract_error_message(response.json())
    except (httpx.HTTPError, ValueError, TypeError):
        return str(exc)


def _looks_like_odata_base(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    # Datacenter hosts: api4.successfactors.com, api16.sapsf.eu, …
    if "successfactors.com" in host or "sapsf." in host:
        return True
    # Rare custom reverse-proxies that already include /odata in the base.
    return "/odata" in (parsed.path or "").lower()


def _first_str(source: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw = source.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None
