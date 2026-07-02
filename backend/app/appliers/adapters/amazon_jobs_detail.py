"""Amazon Jobs public job detail lookup for apply previews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.appliers.adapters.amazon_jobs_common import (
    account_apply_url,
    apply_page_url,
    job_search_url,
)
from app.scrapers.http import HttpClient


@dataclass(frozen=True, slots=True)
class AmazonJobDetail:
    """Normalized amazon.jobs posting used by the apply adapter."""

    job_id: str
    title: str
    company: str
    location: str
    country_code: str | None
    apply_url: str
    account_apply_url: str
    raw: dict[str, Any]


def fetch_public_job_detail(
    http: HttpClient,
    *,
    locale: str,
    job_id: str,
) -> AmazonJobDetail:
    """Load one posting from the public search.json API."""
    data = http.get_json(
        job_search_url(locale, job_id),
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    if not isinstance(data, dict):
        raise ValueError("amazon_jobs search.json returned unexpected payload")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError(f"amazon_jobs job {job_id} was not found in search.json")
    job = jobs[0]
    if not isinstance(job, dict):
        raise ValueError("amazon_jobs search.json returned an invalid job record")
    resolved_id = str(job.get("id_icims") or job.get("id") or job_id).strip()
    if resolved_id != str(job_id).strip():
        raise ValueError(f"amazon_jobs search.json returned job {resolved_id}, expected {job_id}")
    title = str(job.get("title") or "").strip()
    company = str(job.get("company_name") or "Amazon").strip() or "Amazon"
    location = str(job.get("normalized_location") or job.get("location") or "").strip()
    country_code = job.get("country_code")
    next_step = str(job.get("url_next_step") or "").strip()
    apply_url = next_step or apply_page_url(job_id)
    return AmazonJobDetail(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        country_code=str(country_code).strip() if country_code else None,
        apply_url=apply_url,
        account_apply_url=account_apply_url(job_id),
        raw=job,
    )
