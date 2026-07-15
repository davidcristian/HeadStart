"""Helpers for recording apply-outcome metadata used by inbox triage (Phase 20)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.models.base import utcnow
from app.models.seen_job import SeenJob
from app.schemas.profile import ResumeFile

# Credential-bearing keys that must never land in plaintext application_log.payload
# (SVC-11). Matched case-insensitively; covers site_credential shape + common aliases.
_SENSITIVE_ADAPTER_PAYLOAD_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "cookies",
        "headers",
        "password",
        "secret",
        "session",
        "session_token",
        "sessiontoken",
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "api_token",
        "apitoken",
        "api_key",
        "apikey",
        "set-cookie",
        "set_cookie",
    }
)


def employer_domain_from_url(url: str) -> str:
    """Return a normalized hostname for matching recruiter email threads."""
    host = urlparse(url).hostname or ""
    return host.lower().removeprefix("www.")


def application_user_consent_payload(*, live_submission: bool) -> dict[str, Any]:
    """Auditable HeadStart opt-in evidence stamped on each application_log."""
    return {
        "user_consent": {
            "basis": "consent",
            "mechanism": ("source.auto_apply_enabled" if live_submission else "dry_run_preview"),
            "live_submission": live_submission,
            "recorded_at": utcnow().isoformat().replace("+00:00", "Z"),
        }
    }


def application_tracking_payload(
    job: SeenJob,
    *,
    live_submission: bool | None = None,
) -> dict[str, Any]:
    """Baseline posting metadata stored on every application_log row."""
    payload: dict[str, Any] = {
        "employer_domain": employer_domain_from_url(job.url),
        "posting": {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "external_id": job.external_id,
        },
    }
    if live_submission is not None:
        payload.update(application_user_consent_payload(live_submission=live_submission))
    return payload


def _scrub_payload_value(value: Any) -> Any:
    """Recursively scrub nested dict/list values."""
    if isinstance(value, dict):
        return scrub_adapter_payload(value)
    if isinstance(value, list):
        return [_scrub_payload_value(item) for item in value]
    return value


def scrub_adapter_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop credential-bearing keys from an adapter payload before DB persist."""
    scrubbed: dict[str, Any] = {}
    for key, item in payload.items():
        if str(key).lower() in _SENSITIVE_ADAPTER_PAYLOAD_KEYS:
            continue
        scrubbed[str(key)] = _scrub_payload_value(item)
    return scrubbed


def merge_application_log_payload(
    job: SeenJob,
    adapter_payload: dict[str, Any] | None,
    *,
    dry_run: bool,
    tailored_resume: ResumeFile | None = None,
    prior_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge tracking, scrubbed adapter body, and preserved queue-time consent."""
    tracking = application_tracking_payload(job, live_submission=not dry_run)
    consent = tracking["user_consent"]
    if prior_payload is not None and prior_payload.get("user_consent") is not None:
        consent = prior_payload["user_consent"]
    if tailored_resume is not None:
        tracking["tailored_resume"] = {
            "filename": tailored_resume.filename,
            "size_bytes": tailored_resume.size_bytes,
            "content_type": tailored_resume.content_type,
        }
    if adapter_payload:
        tracking = {**tracking, **scrub_adapter_payload(adapter_payload)}
    tracking["user_consent"] = consent
    return tracking
