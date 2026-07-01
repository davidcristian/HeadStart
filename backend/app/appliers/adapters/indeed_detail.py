"""Indeed viewjob page parsing helpers for the apply adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.scrapers.adapters.indeed_parse import _balanced_json_object, reject_captcha

_INITIAL_DATA_MARKER = "window._initialData = "


@dataclass(frozen=True, slots=True)
class IndeedJobDetail:
    """Apply metadata extracted from an Indeed job detail page."""

    job_key: str
    title: str
    company: str
    external_apply_url: str | None
    easily_apply: bool
    indeed_applyable_job_id: str | None
    apply_continue_url: str | None
    expired: bool


def parse_viewjob_page(html: str, *, fallback_job_key: str = "") -> IndeedJobDetail | None:
    """Extract apply metadata embedded in an Indeed /viewjob page."""
    reject_captcha(html)
    initial = extract_initial_data(html)
    if initial is None:
        return None
    return _initial_to_detail(initial, fallback_job_key=fallback_job_key)


def extract_initial_data(html: str) -> dict[str, Any] | None:
    """Parse the `window._initialData` object from an Indeed HTML response."""
    idx = html.find(_INITIAL_DATA_MARKER)
    if idx == -1:
        return None
    start = html.find("{", idx + len(_INITIAL_DATA_MARKER))
    if start == -1:
        return None
    blob = _balanced_json_object(html, start)
    if blob is None:
        return None
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def resolve_viewjob_url(job_external_id: str, job_url: str, config: dict[str, Any]) -> str:
    """Canonical viewjob URL for a scraped Indeed posting."""
    if job_url and "viewjob" in job_url:
        return job_url
    host = str(config.get("host") or "www.indeed.com").strip()
    if host.startswith("http://") or host.startswith("https://"):
        origin = host.rstrip("/")
    else:
        origin = f"https://{host}"
    return f"{origin}/viewjob?jk={job_external_id}"


def _initial_to_detail(initial: dict[str, Any], *, fallback_job_key: str) -> IndeedJobDetail | None:
    job_key = str(initial.get("jobKey") or fallback_job_key or "").strip()
    title = str(initial.get("jobTitle") or "").strip()
    company = _company_name(initial)
    external_url = _external_apply_url(initial)
    apply_attrs = _indeed_apply_attributes(initial)
    easily_apply = apply_attrs is not None
    applyable_id = None
    continue_url = None
    if apply_attrs:
        applyable_id = str(apply_attrs.get("indeedApplyableJobId") or "").strip() or None
        continue_url = str(apply_attrs.get("continueUrl") or "").strip() or None
        if not job_key:
            job_key = str(apply_attrs.get("jk") or "").strip()
    if not job_key:
        job_key = _job_key_from_host_query(initial) or fallback_job_key
    if not title:
        title = _title_from_host_query(initial)
    if not job_key or not title:
        return None
    expired = bool(_job_field(initial, "expired"))
    return IndeedJobDetail(
        job_key=job_key,
        title=title,
        company=company,
        external_apply_url=external_url,
        easily_apply=easily_apply,
        indeed_applyable_job_id=applyable_id,
        apply_continue_url=continue_url,
        expired=expired,
    )


def _company_name(initial: dict[str, Any]) -> str:
    header = initial.get("jobInfoWrapperModel")
    if isinstance(header, dict):
        job_info = header.get("jobInfoModel")
        if isinstance(job_info, dict):
            header_model = job_info.get("jobInfoHeaderModel")
            if isinstance(header_model, dict):
                name = header_model.get("companyName")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    employer = _job_field(initial, "sourceEmployerName")
    return str(employer or "").strip()


def _external_apply_url(initial: dict[str, Any]) -> str | None:
    raw = _job_field(initial, "url")
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url or _is_indeed_url(url):
        return None
    return url


def _indeed_apply_attributes(initial: dict[str, Any]) -> dict[str, Any] | None:
    container = initial.get("indeedApplyButtonContainer")
    if not isinstance(container, dict):
        return None
    attrs = container.get("indeedApplyButtonAttributes")
    return attrs if isinstance(attrs, dict) else None


def _job_key_from_host_query(initial: dict[str, Any]) -> str:
    key = _job_field(initial, "key")
    return str(key or "").strip()


def _title_from_host_query(initial: dict[str, Any]) -> str:
    title = _job_field(initial, "title")
    return str(title or "").strip()


def _job_field(initial: dict[str, Any], field: str) -> Any:
    host = initial.get("hostQueryExecutionResult")
    if not isinstance(host, dict):
        return None
    data = host.get("data")
    if not isinstance(data, dict):
        return None
    job_data = data.get("jobData")
    if not isinstance(job_data, dict):
        return None
    results = job_data.get("results")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    job = first.get("job")
    if not isinstance(job, dict):
        return None
    return job.get(field)


def _is_indeed_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "indeed.com" or host.endswith(".indeed.com")
