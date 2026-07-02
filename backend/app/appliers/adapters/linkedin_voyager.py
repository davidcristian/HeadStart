"""Authenticated Voyager lookups for LinkedIn apply routing."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.linkedin_common import (
    build_graphql_url,
    decode_linkedin_redirect,
    has_linkedin_session_cookies,
    voyager_request_cookies,
    voyager_request_headers,
)
from app.appliers.adapters.linkedin_detail import extract_company_apply_url
from app.scrapers.http import HttpClient

_JOB_POSTINGS_QUERY_ID = "voyagerJobsDashJobPostings.891aed7916d7453a37e4bbf5f1f60de4"
_JOB_POSTINGS_QUERY_NAME = "JobPostingDetailSectionsByCardSectionTypesV2"
_LEGACY_DECORATION = "com.linkedin.voyager.deco.jobs.web.shared.WebLightJobPosting-23"
_LEGACY_JOB_URL = "https://www.linkedin.com/voyager/api/jobs/jobPostings/{job_id}"


def fetch_company_apply_url(
    http: HttpClient,
    job_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> str | None:
    """Resolve an employer apply URL for offsite LinkedIn listings when logged in."""
    if not has_linkedin_session_cookies(credentials):
        return None

    url = fetch_company_apply_url_via_graphql(http, job_id, credentials)
    if url:
        return url
    return fetch_company_apply_url_via_legacy(http, job_id, credentials)


def fetch_company_apply_url_via_graphql(
    http: HttpClient,
    job_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> str | None:
    """Read companyApplyUrl from the JobsDash GraphQL job posting query."""
    variables = {"jobPostingUrn": f"urn:li:fsd_jobPosting:{job_id}"}
    url = build_graphql_url(
        query_id=_JOB_POSTINGS_QUERY_ID,
        query_name=_JOB_POSTINGS_QUERY_NAME,
        variables=variables,
    )
    payload = _authenticated_json(http, url, credentials)
    if not isinstance(payload, dict):
        return None
    raw = extract_company_apply_url(payload)
    return decode_linkedin_redirect(raw) if raw else None


def fetch_company_apply_url_via_legacy(
    http: HttpClient,
    job_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> str | None:
    """Fallback to the legacy REST jobPostings endpoint."""
    url = _LEGACY_JOB_URL.format(job_id=job_id)
    payload = _authenticated_json(
        http,
        url,
        credentials,
        params={"decorationId": _LEGACY_DECORATION},
    )
    if not isinstance(payload, dict):
        return None
    raw = extract_company_apply_url(payload)
    return decode_linkedin_redirect(raw) if raw else None


def fetch_application_form(
    http: HttpClient,
    job_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> dict[str, Any] | None:
    """Fetch the Easy Apply form payload for a LinkedIn-hosted posting."""
    if not has_linkedin_session_cookies(credentials):
        return None
    variables = {"jobPostingUrn": f"urn:li:fsd_jobPosting:{job_id}"}
    url = build_graphql_url(
        query_id="voyagerJobsDashOnsiteApplyApplication.5c510b89e31d8b37dda7777374a4adbd",
        query_name="JobsOnsiteApplyApplicationByJobPosting",
        variables=variables,
    )
    payload = _authenticated_json(http, url, credentials)
    return payload if isinstance(payload, dict) else None


def _authenticated_json(
    http: HttpClient,
    url: str,
    credentials: dict[str, dict[str, str]] | None,
    *,
    params: dict[str, str] | None = None,
) -> Any:
    headers = voyager_request_headers(credentials)
    cookies = voyager_request_cookies(credentials)
    if params:
        return http.get_json(url, headers=headers, cookies=cookies, params=params)
    return http.get_json(url, headers=headers, cookies=cookies)
