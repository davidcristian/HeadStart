"""Build SmartRecruiters Application API candidate payloads."""

from __future__ import annotations

import base64
from typing import Any

from app.appliers.adapters.smartrecruiters_common import split_name
from app.appliers.adapters.smartrecruiters_configuration import consent_decisions
from app.appliers.adapters.smartrecruiters_questions import build_screening_answers
from app.appliers.resume import resume_meta_for_payload
from app.appliers.text import render_cover_letter
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile


def build_message_to_hiring_manager(
    profile: ProfileData,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
    include_resume_text: bool = True,
) -> str | None:
    """Cover letter override/template plus optional resume text."""
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
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    config: dict[str, Any],
    configuration: dict[str, Any] | None,
    cover_letter: str | None = None,
    resume_file: ResumeFile | None = None,
    include_file_bytes: bool = True,
) -> dict[str, Any]:
    """Map profile data to the SmartRecruiters candidate application shape."""
    if resume_file is None and isinstance(profile, ApplyProfile):
        resume_file = profile.resume_file

    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not email:
        raise ValueError("profile full_name and email are required to apply")

    payload: dict[str, Any] = {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
    }

    phone = profile.phone.strip()
    if phone:
        payload["phoneNumber"] = phone

    location = profile.location.strip()
    if location:
        payload["location"] = {"fullLocation": location}

    web: dict[str, str] = {}
    linkedin = profile.links.linkedin.strip()
    website = profile.links.website.strip()
    if linkedin:
        web["linkedIn"] = linkedin
    if website:
        web["website"] = website
    if web:
        payload["web"] = web

    message = build_message_to_hiring_manager(
        profile,
        company=company,
        job_title=job_title,
        cover_letter=cover_letter,
        include_resume_text=resume_file is None,
    )
    if message:
        payload["messageToHiringManager"] = message

    consent = consent_decisions(configuration, config)
    if consent is not None:
        payload["consentDecisions"] = consent

    if configuration is not None:
        payload["answers"] = build_screening_answers(configuration, profile.answers)

    if resume_file is not None:
        resume_meta = resume_meta_for_payload(resume_file)
        if resume_meta is not None:
            payload["resume_file"] = resume_meta
        if include_file_bytes:
            payload["resume"] = {
                "fileName": resume_file.filename,
                "mimeType": resume_file.content_type,
                "fileContent": base64.b64encode(resume_file.data).decode("ascii"),
            }

    return payload


def extract_application_id(response: Any) -> str | None:
    """Application id from a successful SmartRecruiters response."""
    if not isinstance(response, dict):
        return None
    app_id = response.get("applicationId") or response.get("id")
    return str(app_id) if app_id is not None else None


def extract_error_message(response: Any) -> str:
    """Best-effort error string from a SmartRecruiters error payload."""
    if isinstance(response, dict):
        message = response.get("message")
        if message:
            return str(message)
        errors = response.get("errors")
        if isinstance(errors, list) and errors:
            return "; ".join(str(item) for item in errors)
    return "smartrecruiters apply rejected the submission"
