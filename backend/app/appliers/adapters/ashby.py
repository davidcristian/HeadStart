"""Ashby job-board apply adapter.

Submits applications via the Ashby RPC API:
  POST https://api.ashbyhq.com/applicationForm.submit

Config / context:
  - `config["ashby_api_key"]`: Ashby API key with `candidatesWrite` for live submission.
  - Credential `session["ashby_api_key"]` overrides the config value.
  - `config["cover_letter_path"]`: optional form field path for cover letter + resume text.
  - `config["phone_path"]`: optional form field path for the profile phone number.
  - `config["location_path"]`: optional form field path for the profile location string.
  - `config["resume_path"]`: optional form field path for resume file
    (default `_systemfield_resume`).

Live submission requires an organization API key (Admin → Settings → API). Use
`dry_run=True` to preview the JSON payload without a key. Resume files use
multipart/form-data on live submit.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.appliers.adapters.ashby_response import (
    extract_application_id,
    extract_blocked_message,
    extract_error_message,
)
from app.appliers.adapters.ashby_structured import append_structured_profile_submissions
from app.appliers.base import Applier, register_applier
from app.appliers.resume import resume_meta_for_payload
from app.appliers.types import ApplyContext, ApplyResult
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile

ASHBY_APPLY_URL = "https://api.ashbyhq.com/applicationForm.submit"
_ASHBY_JOB_URL_RE = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/", re.IGNORECASE)


@register_applier("ashby")
class AshbyApplier(Applier):
    """Submit applications to an Ashby public job board."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        try:
            built = build_application_payload(
                ctx.job_external_id,
                ctx.profile,
                ctx.job_title,
                ctx.company,
                ctx.config,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        payload = built["payload"]
        multipart = built.get("multipart")

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        api_key = resolve_api_key(ctx.credentials, ctx.config)
        if not api_key:
            return ApplyResult(
                status="failed",
                error=(
                    "ashby live apply requires an API key in "
                    "credential session.ashby_api_key or config.ashby_api_key"
                ),
                payload=payload,
            )

        headers = {"Authorization": basic_auth_header(api_key)}
        try:
            if multipart is not None:
                response = self.http.post_multipart(
                    ASHBY_APPLY_URL,
                    data=multipart["data"],
                    files=multipart["files"],
                    headers=headers,
                )
            else:
                response = self.http.post_json(ASHBY_APPLY_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        if isinstance(response, dict) and response.get("success") is False:
            return ApplyResult(
                status="failed",
                error=extract_error_message(response),
                payload=payload,
            )

        blocked_message = extract_blocked_message(response)
        if blocked_message:
            return ApplyResult(status="failed", error=blocked_message, payload=payload)

        app_id = extract_application_id(response)
        return ApplyResult(status="submitted", payload=payload, external_application_id=app_id)


def resolve_board(config: dict[str, Any], job_url: str) -> str | None:
    """Ashby board slug from config or a standard careers URL."""
    board = config.get("board") or config.get("site")
    if board:
        return str(board)
    match = _ASHBY_JOB_URL_RE.search(job_url)
    return match.group(1) if match else None


def resolve_api_key(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Ashby API key from credential session or source config."""
    if credentials:
        session_key = (credentials.get("session") or {}).get("ashby_api_key")
        if session_key:
            return str(session_key)
    config_key = config.get("ashby_api_key")
    return str(config_key) if config_key else None


def basic_auth_header(api_key: str) -> str:
    """Ashby expects HTTP Basic auth with the API key as username."""
    encoded = base64.b64encode(f"{api_key}:".encode()).decode()
    return f"Basic {encoded}"


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
    include_resume_text: bool = True,
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

    return "\n\n".join(parts) if parts else None


def build_application_payload(
    job_posting_id: str,
    profile: ProfileData | ApplyProfile,
    job_title: str,
    company: str,
    config: dict[str, Any],
    *,
    cover_letter: str | None = None,
    resume_file: ResumeFile | None = None,
) -> dict[str, Any]:
    """Map profile data to the Ashby applicationForm.submit shape."""
    if resume_file is None and isinstance(profile, ApplyProfile):
        resume_file = profile.resume_file
    name = profile.full_name.strip()
    email = profile.email.strip()
    if not name:
        raise ValueError("profile full_name is required to apply")
    if not email:
        raise ValueError("profile email is required to apply")

    submissions: list[dict[str, Any]] = [
        {"path": "_systemfield_name", "value": name},
        {"path": "_systemfield_email", "value": email},
    ]
    used_paths = {"_systemfield_name", "_systemfield_email"}

    phone_path = config.get("phone_path")
    phone = profile.phone.strip()
    if phone_path and phone:
        submissions.append({"path": str(phone_path), "value": phone})
        used_paths.add(str(phone_path))

    location_path = config.get("location_path")
    location = profile.location.strip()
    if location_path and location:
        submissions.append({"path": str(location_path), "value": location})
        used_paths.add(str(location_path))

    cover_letter_path = config.get("cover_letter_path")
    supplemental = build_supplemental_text(
        profile,
        company=company,
        job_title=job_title,
        cover_letter=cover_letter,
        include_resume_text=resume_file is None,
    )
    if cover_letter_path and supplemental:
        submissions.append({"path": str(cover_letter_path), "value": supplemental})
        used_paths.add(str(cover_letter_path))

    resume_path = str(config.get("resume_path") or "_systemfield_resume")
    resume_field_key = "resume_1"
    if resume_file is not None:
        submissions.append({"path": resume_path, "value": resume_field_key})
        used_paths.add(resume_path)

    append_structured_profile_submissions(submissions, used_paths, profile, config)

    for key, value in profile.answers.items():
        if not value or key in used_paths:
            continue
        submissions.append({"path": key, "value": value})

    payload: dict[str, Any] = {
        "jobPostingId": job_posting_id,
        "applicationForm": {"fieldSubmissions": submissions},
    }

    if config.get("allow_unpublished_job_posting") is False:
        payload["allowSubmissionForUnpublishedJobPosting"] = False

    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume_file"] = meta

    result: dict[str, Any] = {"payload": payload}
    if resume_file is not None:
        result["multipart"] = {
            "data": {
                "applicationForm": json.dumps({"fieldSubmissions": submissions}),
                "jobPostingId": job_posting_id,
            },
            "files": {
                resume_field_key: (
                    resume_file.filename,
                    resume_file.data,
                    resume_file.content_type,
                )
            },
        }
    return result
