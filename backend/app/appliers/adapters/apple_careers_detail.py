"""Apple Careers job-detail page parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.appliers.adapters.apple_careers_common import DEFAULT_LOCALE
from app.scrapers.adapters.apple_careers_parse import extract_hydration_data
from app.scrapers.http import HttpClient


@dataclass(frozen=True, slots=True)
class AppleCareersJobDetail:
    """Apply metadata extracted from a jobs.apple.com detail page."""

    position_id: str
    job_number: str
    title: str
    job_type: str
    pipeline_type: str | None
    role_location_selection: bool
    managed_pipeline_role: bool
    transformed_posting_title: str
    locale: str
    locations: tuple[dict[str, Any], ...]


def fetch_job_detail(http: HttpClient, detail_url: str) -> AppleCareersJobDetail:
    """Load and parse a public Apple Careers job detail page."""
    html = http.get_text(detail_url)
    return parse_job_detail_page(html)


def parse_job_detail_page(html: str) -> AppleCareersJobDetail:
    """Parse jobsData embedded in a job detail hydration payload."""
    data = extract_hydration_data(html)
    loader = data.get("loaderData")
    if not isinstance(loader, dict):
        raise ValueError("apple_careers job detail is missing loaderData")
    job_details = loader.get("jobDetails")
    if not isinstance(job_details, dict):
        raise ValueError("apple_careers job detail is missing jobDetails loader data")
    jobs_data = job_details.get("jobsData")
    if not isinstance(jobs_data, dict):
        raise ValueError("apple_careers job detail is missing jobsData")
    return _to_detail(jobs_data, loader=loader)


def _to_detail(jobs_data: dict[str, Any], *, loader: dict[str, Any]) -> AppleCareersJobDetail:
    position_id = str(jobs_data.get("id") or jobs_data.get("reqId") or "").strip()
    if not position_id:
        raise ValueError("apple_careers job detail is missing position id")
    title = str(jobs_data.get("postingTitle") or "").strip()
    job_number = str(jobs_data.get("jobNumber") or jobs_data.get("reqId") or position_id).strip()
    locations = jobs_data.get("locations")
    if not isinstance(locations, list):
        locations = []
    locale = DEFAULT_LOCALE
    root = loader.get("root")
    if isinstance(root, dict) and root.get("locale"):
        locale = str(root["locale"]).strip().lower()
    locale_info = jobs_data.get("localeInfo")
    if isinstance(locale_info, dict) and locale_info.get("defaultLocaleCode"):
        locale = str(locale_info["defaultLocaleCode"]).strip().lower()
    pipeline_type = jobs_data.get("pipelineType")
    return AppleCareersJobDetail(
        position_id=position_id,
        job_number=job_number,
        title=title,
        job_type=str(jobs_data.get("type") or "").strip(),
        pipeline_type=str(pipeline_type).strip() if pipeline_type else None,
        role_location_selection=bool(jobs_data.get("roleLocationSelection")),
        managed_pipeline_role=bool(jobs_data.get("managedPipelineRole")),
        transformed_posting_title=str(jobs_data.get("transformedPostingTitle") or "").strip(),
        locale=locale,
        locations=tuple(item for item in locations if isinstance(item, dict)),
    )
