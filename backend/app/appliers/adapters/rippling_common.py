"""Shared helpers for the Rippling ATS apply adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

_API_HOST = "api.rippling.com"
_ATS_HOST = "ats.rippling.com"
_API_PREFIX = "/platform/api/ats/v1"
_BOARD_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")
_JOB_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def api_base() -> str:
    """Public Rippling ATS API origin + version prefix."""
    return f"https://{_API_HOST}{_API_PREFIX}"


def job_detail_url(board: str, job_id: str) -> str:
    """GET URL for a single public board job (includes apply questions)."""
    return f"{api_base()}/board/{board}/jobs/{job_id}"


def apply_url(board: str, job_id: str) -> str:
    """POST URL for submitting a public board application."""
    return f"{api_base()}/board/{board}/jobs/{job_id}/apply"


def file_upload_url() -> str:
    """GET URL that returns a presigned S3 POST for resume/cover-letter files."""
    return f"{api_base()}/utility/file_upload_url"


def resolve_board(config: dict[str, Any], job_url: str) -> str | None:
    """Board slug from config or an ats.rippling.com / board API URL."""
    board = str(config.get("board") or "").strip()
    if board and _BOARD_RE.fullmatch(board):
        return board
    if not job_url:
        return None
    parsed = urlparse(job_url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host == _ATS_HOST and parts:
        candidate = parts[0]
        return candidate if _BOARD_RE.fullmatch(candidate) else None
    if host == _API_HOST and len(parts) >= 6 and "/".join(parts[:5]) == "platform/api/ats/v1/board":
        candidate = parts[5]
        return candidate if _BOARD_RE.fullmatch(candidate) else None
    return None


def resolve_job_id(config: dict[str, Any], job_external_id: str, job_url: str) -> str | None:
    """Job UUID from external id, config override, or careers URL path."""
    for raw in (config.get("job_id"), config.get("uuid"), job_external_id):
        candidate = str(raw or "").strip()
        if candidate and _JOB_UUID_RE.fullmatch(candidate):
            return candidate
    if not job_url:
        return None
    parsed = urlparse(job_url)
    parts = [part for part in parsed.path.split("/") if part]
    # /<board>/jobs/<uuid> or /.../board/<board>/jobs/<uuid>
    if "jobs" in parts:
        idx = parts.index("jobs")
        if idx + 1 < len(parts) and _JOB_UUID_RE.fullmatch(parts[idx + 1]):
            return parts[idx + 1]
    query_id = parse_qs(parsed.query).get("jobId") or parse_qs(parsed.query).get("job_id")
    if query_id and _JOB_UUID_RE.fullmatch(query_id[0]):
        return query_id[0]
    return None


def turnstile_token(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Cloudflare Turnstile token for live public-board submit."""
    session = (credentials or {}).get("session") or {}
    for key in ("cf_turnstile_token", "turnstile_token", "cf_client_response"):
        value = str(session.get(key) or config.get(key) or "").strip()
        if value:
            return value
    return None


def turnstile_headers(token: str, *, status: str = "success") -> dict[str, str]:
    """Headers the careers UI attaches when Turnstile verification succeeds."""
    return {
        "cf-client-response": token,
        "cf-client-response-status": status,
    }
