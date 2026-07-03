"""Greenhouse job-board apply adapter.

Submits applications via the public Job Board API:
  POST https://boards-api.greenhouse.io/v1/boards/<board_token>/jobs/<id>

Config / context:
  - `config["board_token"]`: board slug (optional if derivable from `job_url`).
  - `config["job_board_api_key"]`: Job Board API key for live submission.
  - Credential `session["job_board_api_key"]` overrides the config value.

Live submission requires a per-board Job Board API key (created in the employer's
Greenhouse admin). Use `dry_run=True` to preview the JSON payload without a key.
"""

from __future__ import annotations

import base64
import re
from typing import Any

import httpx

from app.appliers.adapters.greenhouse_structured import (
    build_education_lookup_resolver,
    build_employments,
)
from app.appliers.base import Applier, register_applier
from app.appliers.resume import greenhouse_resume_fields, resume_meta_for_payload
from app.appliers.types import ApplyContext, ApplyResult
from app.schemas.profile import ApplyProfile, ProfileData

GREENHOUSE_APPLY_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
_BOARD_URL_RE = re.compile(r"boards\.greenhouse\.io/([^/]+)/jobs/", re.IGNORECASE)


@register_applier("greenhouse")
class GreenhouseApplier(Applier):
    """Submit applications to a Greenhouse public job board."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        board_token = resolve_board_token(ctx.config, ctx.job_url)
        if not board_token:
            return ApplyResult(
                status="failed",
                error=(
                    "greenhouse applier needs config.board_token "
                    "or a boards.greenhouse.io job URL"
                ),
            )

        resolver = build_education_lookup_resolver(
            self.http,
            board_token=board_token,
            config=ctx.config,
        )
        educations: list[dict[str, Any]] = []
        if not ctx.config.get("skip_education") and resolver is not None:
            educations = resolver.resolve_all(ctx.profile)
        employments: list[dict[str, Any]] = []
        if not ctx.config.get("skip_work_experience"):
            employments = build_employments(ctx.profile)

        try:
            payload = build_application_payload(
                ctx.profile,
                ctx.job_title,
                ctx.company,
                ctx.config,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
                include_resume_bytes=not ctx.dry_run,
                employments=employments,
                educations=educations,
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
                    "greenhouse live apply requires a Job Board API key in "
                    "credential session.job_board_api_key or config.job_board_api_key"
                ),
                payload=payload,
            )

        url = GREENHOUSE_APPLY_URL.format(board_token=board_token, job_id=ctx.job_external_id)
        headers = {"Authorization": basic_auth_header(api_key)}
        try:
            response = self.http.post_json(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        app_id = _extract_application_id(response)
        return ApplyResult(status="submitted", payload=payload, external_application_id=app_id)


def resolve_board_token(config: dict[str, Any], job_url: str) -> str | None:
    """Board slug from config or a standard Greenhouse careers URL."""
    token = config.get("board_token")
    if token:
        return str(token)
    match = _BOARD_URL_RE.search(job_url)
    return match.group(1) if match else None


def resolve_api_key(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """Job Board API key from credential session or source config."""
    if credentials:
        session_key = (credentials.get("session") or {}).get("job_board_api_key")
        if session_key:
            return str(session_key)
    config_key = config.get("job_board_api_key")
    return str(config_key) if config_key else None


def basic_auth_header(api_key: str) -> str:
    """Greenhouse expects HTTP Basic auth with the API key as username."""
    encoded = base64.b64encode(f"{api_key}:".encode()).decode()
    return f"Basic {encoded}"


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


def build_application_payload(
    profile: ProfileData | ApplyProfile,
    job_title: str,
    company: str,
    config: dict[str, Any],
    *,
    cover_letter: str | None = None,
    resume_file: Any = None,
    include_resume_bytes: bool = True,
    employments: list[dict[str, Any]] | None = None,
    educations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Map profile data to the Greenhouse Job Board application JSON shape."""
    if resume_file is None and isinstance(profile, ApplyProfile):
        resume_file = profile.resume_file
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    payload: dict[str, Any] = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
    }

    phone = profile.phone.strip()
    if phone:
        payload["phone"] = phone

    location = profile.location.strip()
    if location:
        payload["location"] = location

    resume_text = profile.resume_text.strip()
    if resume_text and resume_file is None:
        payload["resume_text"] = resume_text

    if include_resume_bytes:
        payload.update(greenhouse_resume_fields(resume_file))

    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume_file"] = meta

    if cover_letter and cover_letter.strip():
        payload["cover_letter_text"] = cover_letter.strip()
    else:
        cover_template = profile.cover_letter_template.strip()
        if cover_template:
            payload["cover_letter_text"] = render_cover_letter(
                cover_template, company=company, job_title=job_title
            )

    for key, value in profile.answers.items():
        if not value:
            continue
        if key.startswith("question_") or key.startswith("data_compliance"):
            payload[key] = value

    if config.get("gdpr_consent"):
        payload["data_compliance"] = {
            "gdpr_processing_consent_given": True,
            "gdpr_retention_consent_given": True,
        }

    if employments:
        payload["employments"] = employments
    if educations:
        payload["educations"] = educations

    return payload


def _extract_application_id(response: Any) -> str | None:
    if isinstance(response, dict):
        for key in ("id", "application_id"):
            if response.get(key) is not None:
                return str(response[key])
    return None
