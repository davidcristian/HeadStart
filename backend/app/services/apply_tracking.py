"""Helpers for recording apply-outcome metadata used by inbox triage (Phase 20)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.models.seen_job import SeenJob


def employer_domain_from_url(url: str) -> str:
    """Return a normalized hostname for matching recruiter email threads."""
    host = urlparse(url).hostname or ""
    return host.lower().removeprefix("www.")


def application_tracking_payload(job: SeenJob) -> dict[str, Any]:
    """Baseline posting metadata stored on every application_log row."""
    return {
        "employer_domain": employer_domain_from_url(job.url),
        "posting": {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "external_id": job.external_id,
        },
    }
