"""Shared Workday CXS helpers for the apply adapter.

Workday career sites expose a public Candidate Experience Service (CXS) API.
Job listings use POST ``/wday/cxs/{tenant}/{site}/jobs``; applications use
authenticated endpoints under ``/wday/cxs/{tenant}/jobpostings/...`` and
``/wday/cxs/{tenant}/jobapplication/...`` with session cookies and a CSRF token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.schemas.profile import ProfileData
from app.scrapers.http import HttpClient

_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_HOST_WITH_REGION = re.compile(r"^([^.]+)\.(wd\d+)\.myworkdayjobs\.com$", re.IGNORECASE)
_HOST_PLAIN = re.compile(r"^([^.]+)\.myworkdayjobs\.com$", re.IGNORECASE)
_JOB_URL_RE = re.compile(
    r"myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[^/]+/job/(.+)$",
    re.IGNORECASE,
)
CSRF_HEADER = "X-CALYPSO-CSRF-TOKEN"
SESSION_HEADER = "X-Cxs-Session-Id"


@dataclass(frozen=True)
class WorkdayTarget:
    """Resolved Workday tenant/site coordinates."""

    tenant: str
    site: str
    region: str | None
    locale: str
    company: str
    host: str

    @property
    def board_url(self) -> str:
        return f"https://{self.host}/{self.locale}/{self.site}"

    def job_page_url(self, job_path: str) -> str:
        return f"{self.board_url}/job/{job_path}"

    def apply_referer(self, job_path: str) -> str:
        return f"{self.job_page_url(job_path)}/apply"

    def api_base(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}"


def resolve_target(config: dict[str, Any], job_url: str) -> WorkdayTarget | None:
    """Tenant/site coordinates from config or a careers job URL."""
    company = str(config.get("company") or config.get("tenant") or config.get("site") or "")
    locale = str(config.get("locale") or "en-US")
    tenant = str(config.get("tenant") or "")
    site = str(config.get("site") or "")
    region = str(config.get("region") or "") or None

    if job_url:
        try:
            return _from_job_url(job_url, company=company, locale=locale)
        except ValueError:
            return None

    if not tenant or not site:
        return None
    return WorkdayTarget(
        tenant=tenant,
        site=site,
        region=region,
        locale=locale,
        company=company or tenant,
        host=_host(tenant, region),
    )


def resolve_job_path(config: dict[str, Any], job_url: str) -> str | None:
    """CXS job path segment (location/slug) from config or URL."""
    configured = config.get("job_path")
    if configured:
        return str(configured).strip("/")
    if not job_url:
        return None
    match = _JOB_URL_RE.search(job_url)
    if not match:
        return None
    return match.group(1).strip("/")


def resolve_job_posting_id(
    config: dict[str, Any], job_url: str, job_external_id: str
) -> str | None:
    """Workday job posting anchor id used by the apply API."""
    configured = config.get("job_posting_id")
    if configured:
        return str(configured)
    job_path = resolve_job_path(config, job_url)
    if job_path:
        return job_path.rsplit("/", 1)[-1]
    if job_external_id and "_" in job_external_id:
        return job_external_id
    return job_external_id or None


def resolve_csrf_token(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """CSRF token from credential session or cookies."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("csrf_token", "calypso_csrf_token", "CALYPSO_CSRF_TOKEN"):
            value = session.get(key)
            if value:
                return str(value)
        cookies = credentials.get("cookies") or {}
        cookie_token = cookies.get("CALYPSO_CSRF_TOKEN")
        if cookie_token:
            return str(cookie_token)
    config_token = config.get("csrf_token")
    return str(config_token) if config_token else None


def build_http_client(
    credentials: dict[str, dict[str, str]] | None,
    *,
    headers: dict[str, str] | None = None,
) -> HttpClient:
    """HttpClient that carries stored site cookies/headers for CXS calls."""
    cred_headers = (credentials or {}).get("headers") or {}
    cred_cookies = (credentials or {}).get("cookies") or {}
    merged_headers = {**cred_headers, **(headers or {})}
    return HttpClient(headers=merged_headers, cookies=cred_cookies)


def job_posting_info_url(target: WorkdayTarget, job_path: str) -> str:
    """CXS job detail URL used to read questionnaire metadata."""
    return f"https://{target.host}/wday/cxs/{target.tenant}/{target.site}/job/{job_path}"


def calypso_common_url(target: WorkdayTarget, suffix: str) -> str:
    """Calypso common-service URL (questionnaire definitions)."""
    return f"https://{target.host}/wday/calypso/cxs/common/{target.tenant}/{suffix}"


def calypso_jobapplication_url(target: WorkdayTarget, suffix: str) -> str:
    """Calypso jobapplication-service URL (questionnaire submit)."""
    return f"https://{target.host}/wday/calypso/cxs/jobapplication/{target.tenant}/{suffix}"


def cxs_jobapplication_url(target: WorkdayTarget, application_id: str, section: str) -> str:
    """Direct CXS application section URL (name, finalize, terms, ...)."""
    return f"{target.api_base()}/jobapplication/{application_id}/{section}"


def fetch_job_posting_info(
    http: HttpClient, target: WorkdayTarget, job_path: str
) -> dict[str, Any]:
    """Load job posting metadata (questionnaire ids, etc.) from CXS."""
    url = job_posting_info_url(target, job_path)
    headers = {
        "Accept": "application/json",
        "Accept-Language": target.locale,
        "Referer": target.job_page_url(job_path),
    }
    data = http.get_json(url, headers=headers)
    if not isinstance(data, dict):
        return {}
    posting = data.get("jobPostingInfo")
    return posting if isinstance(posting, dict) else {}


def request_headers(
    target: WorkdayTarget,
    job_path: str,
    *,
    csrf_token: str | None,
    session_id: str | None = None,
    form_definition: bool = False,
    credentials: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """Standard CXS headers for apply requests."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": target.locale,
        "Referer": target.apply_referer(job_path),
    }
    if csrf_token:
        headers[CSRF_HEADER] = csrf_token
    if session_id:
        headers[SESSION_HEADER] = session_id
    if form_definition:
        headers["form-definition"] = "true"
    if credentials:
        cred_headers = credentials.get("headers") or {}
        headers.update(cred_headers)
        cookie_header = _cookie_header(credentials.get("cookies") or {})
        if cookie_header:
            headers["Cookie"] = cookie_header
    return headers


def _cookie_header(cookies: dict[str, str]) -> str:
    """Serialize cookie dict for a single Cookie request header."""
    return "; ".join(f"{key}={value}" for key, value in cookies.items())


def split_name(full_name: str) -> tuple[str, str]:
    """Split a display name into first and last components."""
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def render_cover_letter(template: str, *, company: str, job_title: str) -> str:
    """Substitute simple placeholders in a cover-letter template."""
    replacements = {
        "{company}": company,
        "{job_title}": job_title,
        "{title}": job_title,
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def build_supplemental_text(
    profile: ProfileData,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
) -> str | None:
    """Cover letter (override or template) plus optional resume text."""
    parts: list[str] = []
    if cover_letter and cover_letter.strip():
        parts.append(cover_letter.strip())
    else:
        template = profile.cover_letter_template.strip()
        if template:
            parts.append(render_cover_letter(template, company=company, job_title=job_title))

    resume = profile.resume_text.strip()
    if resume:
        parts.append(f"Resume:\n{resume}")

    return "\n\n".join(parts) if parts else None


def build_application_payload(
    profile: ProfileData,
    *,
    job_posting_id: str,
    job_path: str,
    job_title: str,
    company: str,
    config: dict[str, Any],
    cover_letter: str | None = None,
) -> dict[str, Any]:
    """Map profile data to the Workday CXS apply payload shape."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    country_id = str(config.get("country_id") or "US")
    payload: dict[str, Any] = {
        "jobPostingId": job_posting_id,
        "jobPath": job_path,
        "applyMethod": str(config.get("apply_method") or "manual"),
        "candidate": {
            "legalName": {
                "firstName": first_name,
                "lastName": last_name,
                "country": {"id": country_id},
            },
            "emailAddress": email,
        },
    }

    phone = profile.phone.strip()
    if phone:
        payload["candidate"]["phoneNumber"] = phone

    location = profile.location.strip()
    if location:
        payload["candidate"]["location"] = location

    links: dict[str, str] = {}
    if profile.links.linkedin.strip():
        links["linkedIn"] = profile.links.linkedin.strip()
    if profile.links.github.strip():
        links["github"] = profile.links.github.strip()
    if profile.links.website.strip():
        links["website"] = profile.links.website.strip()
    if links:
        payload["candidate"]["links"] = links

    supplemental = build_supplemental_text(
        profile, company=company, job_title=job_title, cover_letter=cover_letter
    )
    if supplemental:
        payload["candidate"]["comments"] = supplemental

    for key, value in profile.answers.items():
        if value:
            payload.setdefault("answers", {})[key] = value

    return payload


def build_name_body(profile: ProfileData, config: dict[str, Any]) -> dict[str, Any]:
    """Body for POST jobapplication/{id}/name."""
    first_name, last_name = split_name(profile.full_name)
    country_id = str(config.get("country_id") or "US")
    return {
        "legalName": {
            "firstName": first_name,
            "lastName": last_name,
            "country": {"id": country_id},
        },
        "preferredCheck": False,
    }


def _from_job_url(job_url: str, *, company: str, locale: str) -> WorkdayTarget:
    parsed = urlparse(job_url)
    host = parsed.netloc.lower()
    tenant, region = _parse_host(host)
    parts = [part for part in parsed.path.split("/") if part]

    if parts and _LOCALE_RE.match(parts[0]):
        locale = parts[0]
        parts = parts[1:]
    if not parts:
        raise ValueError("workday applier could not determine site from job_url")
    site = parts[0]
    if not tenant:
        raise ValueError("workday applier could not determine tenant from job_url")
    return WorkdayTarget(
        tenant=tenant,
        site=site,
        region=region,
        locale=locale,
        company=company or tenant,
        host=host,
    )


def _parse_host(host: str) -> tuple[str, str | None]:
    match = _HOST_WITH_REGION.match(host)
    if match:
        return match.group(1), match.group(2)
    match = _HOST_PLAIN.match(host)
    if match:
        return match.group(1), None
    raise ValueError("workday applier job_url must be a *.myworkdayjobs.com URL")


def _host(tenant: str, region: str | None) -> str:
    if region:
        return f"{tenant}.{region}.myworkdayjobs.com"
    return f"{tenant}.myworkdayjobs.com"
