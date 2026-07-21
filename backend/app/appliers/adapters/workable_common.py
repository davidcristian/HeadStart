"""Shared helpers for the Workable public careers apply adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_APPLY_HOST = "apply.workable.com"
_SHORTCODE_RE = re.compile(r"^[A-Za-z0-9]{6,20}$")
_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")


def form_url(shortcode: str) -> str:
    """GET URL for the public application form schema."""
    return f"https://{_APPLY_HOST}/api/v1/jobs/{shortcode}/form"


def apply_url(shortcode: str) -> str:
    """POST URL for submitting a public careers application."""
    return f"https://{_APPLY_HOST}/api/v1/jobs/{shortcode}/apply"


def resume_upload_url(shortcode: str) -> str:
    """GET URL that returns a presigned S3 POST for the resume field."""
    return f"https://{_APPLY_HOST}/api/v1/jobs/{shortcode}/form/upload/resume"


def resolve_shortcode(config: dict[str, Any], job_external_id: str, job_url: str) -> str | None:
    """Job shortcode from external id, config override, or careers URL path."""
    for raw in (
        config.get("shortcode"),
        config.get("job_id"),
        config.get("job_shortcode"),
        job_external_id,
    ):
        candidate = str(raw or "").strip()
        if candidate and _SHORTCODE_RE.fullmatch(candidate):
            return candidate
    if not job_url:
        return None
    parsed = urlparse(job_url)
    host = (parsed.hostname or "").lower()
    if host != _APPLY_HOST:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    # /j/<shortcode> or /<account>/j/<shortcode>
    if "j" in parts:
        idx = parts.index("j")
        if idx + 1 < len(parts) and _SHORTCODE_RE.fullmatch(parts[idx + 1]):
            return parts[idx + 1]
    return None


def resolve_account(config: dict[str, Any], job_url: str) -> str | None:
    """Optional account slug from config or ``apply.workable.com/<account>/…`` URL."""
    account = str(config.get("account") or "").strip()
    if account and _ACCOUNT_RE.fullmatch(account):
        return account
    if not job_url:
        return None
    parsed = urlparse(job_url)
    host = (parsed.hostname or "").lower()
    if host != _APPLY_HOST:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts or parts[0] in {"api", "j", "jobs", "login", "oauth", "static", "assets"}:
        return None
    if "j" in parts and parts[0] != "j" and _ACCOUNT_RE.fullmatch(parts[0]):
        return parts[0]
    return None


def turnstile_token(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Cloudflare Turnstile token for live public-careers submit."""
    session = (credentials or {}).get("session") or {}
    for key in ("cf_turnstile_token", "turnstile_token", "x_turnstile_token"):
        value = str(session.get(key) or config.get(key) or "").strip()
        if value:
            return value
    return None


def turnstile_headers(token: str) -> dict[str, str]:
    """Headers the careers UI attaches when Turnstile verification succeeds."""
    return {"X-TURNSTILE-TOKEN": token}
