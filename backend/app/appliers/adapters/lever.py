"""Lever job-board apply adapter.

Submits applications via the public Postings API:
  POST https://api.lever.co/v0/postings/<site>/<posting_id>?key=<api_key>

Config / context:
  - `config["site"]`: Lever site slug (optional if derivable from `job_url`).
  - `config["region"]`: optional `"eu"` for the EU API host.
  - `config["postings_api_key"]`: Postings API key for live submission.
  - Credential `session["postings_api_key"]` overrides the config value.

Live submission requires a Postings API key (Super Admin → Integrations). Use
`dry_run=True` to preview the JSON payload without a key. Resume files are not
uploaded in v1, so `resume_text` is appended to `comments` when present.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

import httpx

from app.appliers.base import Applier, register_applier
from app.appliers.resume import (
    flatten_lever_form_fields,
    lever_resume_part,
    resume_meta_for_payload,
)
from app.appliers.structured_profile import build_profile_supplement
from app.appliers.text import render_cover_letter
from app.appliers.types import ApplyContext, ApplyResult
from app.schemas.profile import ApplyProfile, ProfileData, ProfileLinks

LEVER_APPLY_URL = {
    "global": "https://api.lever.co/v0/postings/{site}/{posting_id}",
    "eu": "https://api.eu.lever.co/v0/postings/{site}/{posting_id}",
}
_LEVER_JOB_URL_RE = re.compile(r"jobs\.lever\.co/([^/]+)/", re.IGNORECASE)


@register_applier("lever")
class LeverApplier(Applier):
    """Submit applications to a Lever public job board."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        site = resolve_site(ctx.config, ctx.job_url)
        if not site:
            return ApplyResult(
                status="failed",
                error="lever applier needs config.site or a jobs.lever.co job URL",
            )

        try:
            payload = build_application_payload(
                ctx.profile,
                ctx.job_title,
                ctx.company,
                ctx.config,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        api_key = resolve_api_key(ctx.credentials, ctx.config)
        if not api_key:
            return ApplyResult(
                status="failed",
                error=(
                    "lever live apply requires a Postings API key in "
                    "credential session.postings_api_key or config.postings_api_key"
                ),
                payload=payload,
            )

        region = str(ctx.config.get("region", "global")).lower()
        base = LEVER_APPLY_URL.get(region, LEVER_APPLY_URL["global"])
        path = base.format(site=site, posting_id=ctx.job_external_id)
        url = f"{path}?{urlencode({'key': api_key})}"
        resume_part = lever_resume_part(ctx.resume_file)
        try:
            if resume_part is not None:
                response = self.http.post_multipart(
                    url,
                    data=flatten_lever_form_fields(payload),
                    files=dict([resume_part]),
                )
            else:
                response = self.http.post_json(url, json=payload)
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        if isinstance(response, dict) and response.get("ok") is False:
            return ApplyResult(
                status="failed",
                error=str(response.get("error") or "lever apply rejected"),
                payload=payload,
            )

        app_id = _extract_application_id(response)
        return ApplyResult(status="submitted", payload=payload, external_application_id=app_id)


def resolve_site(config: dict[str, Any], job_url: str) -> str | None:
    """Lever site slug from config or a standard careers URL."""
    site = config.get("site")
    if site:
        return str(site)
    match = _LEVER_JOB_URL_RE.search(job_url)
    return match.group(1) if match else None


def resolve_api_key(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Postings API key from credential session or source config."""
    if credentials:
        session_key = (credentials.get("session") or {}).get("postings_api_key")
        if session_key:
            return str(session_key)
    config_key = config.get("postings_api_key")
    return str(config_key) if config_key else None


def build_urls(links: ProfileLinks) -> dict[str, str]:
    """Map profile links to Lever's urls object."""
    mapping = {
        "LinkedIn": links.linkedin.strip(),
        "GitHub": links.github.strip(),
        "Portfolio": links.website.strip(),
    }
    return {label: url for label, url in mapping.items() if url}


def build_comments(
    profile: ProfileData,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
    include_resume_text: bool = True,
    config: dict[str, Any] | None = None,
) -> str | None:
    """Cover letter (override or template) plus optional resume text."""
    parts: list[str] = []
    if cover_letter and cover_letter.strip():
        parts.append(cover_letter.strip())
    else:
        template = profile.cover_letter_template.strip()
        if template:
            parts.append(render_cover_letter(template, company=company, job_title=job_title))

    if include_resume_text:
        resume = profile.resume_text.strip()
        if resume:
            parts.append(f"Resume:\n{resume}")

    if not (config or {}).get("skip_structured_profile"):
        supplement = build_profile_supplement(profile)
        if supplement:
            parts.append(supplement)

    return "\n\n".join(parts) if parts else None


def build_application_payload(
    profile: ProfileData | ApplyProfile,
    job_title: str,
    company: str,
    config: dict[str, Any],
    *,
    cover_letter: str | None = None,
    resume_file: Any = None,
) -> dict[str, Any]:
    """Map profile data to the Lever Postings apply JSON shape."""
    if resume_file is None and isinstance(profile, ApplyProfile):
        resume_file = profile.resume_file
    name = profile.full_name.strip()
    email = profile.email.strip()
    if not name:
        raise ValueError("profile full_name is required to apply")
    if not email:
        raise ValueError("profile email is required to apply")

    payload: dict[str, Any] = {
        "name": name,
        "email": email,
    }

    phone = profile.phone.strip()
    if phone:
        payload["phone"] = phone

    org = profile.answers.get("current_company", "").strip()
    if org:
        payload["org"] = org

    urls = build_urls(profile.links)
    if urls:
        payload["urls"] = urls

    comments = build_comments(
        profile,
        company=company,
        job_title=job_title,
        cover_letter=cover_letter,
        include_resume_text=resume_file is None,
        config=config,
    )
    if comments:
        payload["comments"] = comments

    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume_file"] = meta

    if config.get("silent_confirmations"):
        payload["silent"] = True

    if config.get("gdpr_consent"):
        payload["consent"] = {"store": True, "marketing": False}

    compliance_policy = config.get("compliance_policy_id")
    if compliance_policy and "consent" in payload:
        payload["consent"]["store"] = {
            "provided": True,
            "compliancePolicyId": str(compliance_policy),
        }

    for key, value in profile.answers.items():
        if not value or key == "current_company":
            continue
        if key.startswith("urls."):
            label = key.removeprefix("urls.")
            payload.setdefault("urls", {})[label] = value

    return payload


def _extract_application_id(response: Any) -> str | None:
    if isinstance(response, dict):
        app_id = response.get("applicationId") or response.get("application_id")
        if app_id is not None:
            return str(app_id)
    return None
