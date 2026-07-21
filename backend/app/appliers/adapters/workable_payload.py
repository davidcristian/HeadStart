"""Build Workable public-careers candidate payloads from a profile."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.workable_answers import (
    answer_present,
    build_answers,
    education_entries,
    experience_entries,
    standard_field_ids,
)
from app.appliers.text import split_name
from app.schemas.profile import ProfileData, ResumeFile


def iter_form_fields(form: object) -> list[dict[str, Any]]:
    """Flatten sectioned form schema into field dicts."""
    if not isinstance(form, list):
        return []
    fields: list[dict[str, Any]] = []
    for section in form:
        if not isinstance(section, dict):
            continue
        raw_fields = section.get("fields")
        if not isinstance(raw_fields, list):
            continue
        for field in raw_fields:
            if isinstance(field, dict):
                fields.append(field)
    return fields


def required_field_ids(form: object) -> list[str]:
    """Required field ids from the public form schema."""
    ids: list[str] = []
    for field in iter_form_fields(form):
        if not field.get("required"):
            continue
        field_id = str(field.get("id") or "").strip()
        if field_id:
            ids.append(field_id)
    return ids


def build_candidate(
    profile: ProfileData,
    *,
    config: dict[str, Any],
    cover_letter: str | None,
    resume_file: ResumeFile | None,
    form: object | None = None,
    resume_url: str | None = None,
    include_resume_meta: bool = True,
) -> dict[str, Any]:
    """Map profile fields into Workable's public ``candidate`` object."""
    first_name, last_name = split_name(profile.full_name)
    candidate: dict[str, Any] = {
        "firstname": first_name,
        "lastname": last_name or first_name,
        "email": profile.email.strip(),
        "phone": profile.phone.strip(),
        "address": profile.location.strip(),
    }
    if cover_letter and cover_letter.strip():
        candidate["cover_letter"] = cover_letter.strip()

    headline = str(config.get("headline") or profile.answers.get("headline") or "").strip()
    if headline:
        candidate["headline"] = headline
    summary = str(config.get("summary") or profile.resume_text or "").strip()
    if summary:
        candidate["summary"] = summary

    experience = experience_entries(profile)
    if experience:
        candidate["experience_entries"] = experience
    education = education_entries(profile)
    if education:
        candidate["education_entries"] = education

    if resume_url:
        candidate["resume"] = resume_url
    elif include_resume_meta and resume_file is not None:
        candidate["resume"] = {
            "name": resume_file.filename or "resume.pdf",
            "content_type": resume_file.content_type,
            "size_bytes": resume_file.size_bytes,
        }

    answers = build_answers(
        profile,
        form_fields=iter_form_fields(form) if form is not None else [],
        config=config,
    )
    if answers:
        candidate["answers"] = answers
    return candidate


def missing_required_fields(
    candidate: dict[str, Any],
    required_ids: list[str],
    *,
    live: bool,
) -> list[str]:
    """Return required form field ids still empty on the candidate payload."""
    standard = standard_field_ids()
    answers = {
        str(item.get("question_key") or "").strip(): item
        for item in candidate.get("answers") or []
        if isinstance(item, dict)
    }
    missing: list[str] = []
    for field_id in required_ids:
        if field_id in standard:
            value = candidate.get(field_id)
            if field_id == "resume":
                if live:
                    if not (isinstance(value, str) and value.strip()):
                        missing.append(field_id)
                elif value in (None, "", {}):
                    missing.append(field_id)
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field_id)
            continue
        answer = answers.get(field_id)
        if not answer_present(answer):
            missing.append(field_id)
    return missing


def extract_application_id(response: object) -> str | None:
    """Best-effort application / candidate id from a success payload."""
    if not isinstance(response, dict):
        return None
    for key in ("id", "candidate_id", "candidateId", "application_id", "applicationId"):
        value = response.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    candidate = response.get("candidate")
    if isinstance(candidate, dict):
        for key in ("id", "candidate_id", "candidateId"):
            value = candidate.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def extract_error_message(response: object) -> str:
    """Human-readable error from a Workable apply failure body."""
    if isinstance(response, str) and response.strip():
        return response.strip()
    if not isinstance(response, dict):
        return "workable apply failed"
    for key in ("error", "message", "detail"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            return "; ".join(str(item) for item in value)
    errors = response.get("errors")
    if isinstance(errors, dict) and errors:
        parts = [f"{key}: {value}" for key, value in errors.items()]
        return "; ".join(parts)
    if isinstance(errors, list) and errors:
        return "; ".join(str(item) for item in errors)
    return "workable apply failed"
