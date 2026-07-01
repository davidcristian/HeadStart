"""Microsoft Careers SmartApply payload builders."""

from __future__ import annotations

import base64
from typing import Any

from app.appliers.adapters.greenhouse import render_cover_letter, split_name
from app.appliers.adapters.microsoft_careers_common import apply_page_url
from app.appliers.resume import resume_meta_for_payload
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile


def build_candidate(
    profile: ProfileData | ApplyProfile,
    *,
    job_title: str,
    company: str,
    cover_letter: str | None = None,
) -> dict[str, Any]:
    """Map application profile fields to SmartApply candidate JSON."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    candidate: dict[str, Any] = {
        "firstname": first_name,
        "lastname": last_name,
        "fullname": profile.full_name.strip(),
        "email": email,
    }

    phone = profile.phone.strip()
    if phone:
        candidate["phone"] = phone

    location = profile.location.strip()
    if location:
        candidate["location"] = location
        candidate["location_detail"] = _location_detail(location)

    linkedin = profile.links.linkedin.strip()
    if linkedin:
        candidate["linkedinUrl"] = linkedin

    summary = _cover_letter_text(
        profile,
        company=company,
        job_title=job_title,
        cover_letter=cover_letter,
    )
    if summary:
        candidate["summary"] = summary

    return candidate


def build_answers(profile: ProfileData | ApplyProfile, questions: dict[str, Any]) -> dict[str, Any]:
    """Map profile.answers onto question ids present in the questionnaire payload."""
    answers = {key: value for key, value in profile.answers.items() if value}
    if answers:
        return answers

    mapped: dict[str, Any] = {}
    for section in _question_sections(questions):
        for question in section.get("questions", []):
            if not isinstance(question, dict):
                continue
            question_id = question.get("questionId")
            if not question_id:
                continue
            key = str(question_id)
            if key in profile.answers and profile.answers[key]:
                mapped[key] = profile.answers[key]
    return mapped


def build_application_payload(
    *,
    domain: str,
    position_id: str,
    job_detail: dict[str, Any],
    questions: dict[str, Any],
    candidate: dict[str, Any],
    answers: dict[str, Any],
    resume_file: ResumeFile | None,
    include_resume_bytes: bool,
) -> dict[str, Any]:
    """Preview payload for dry-run and live submit orchestration."""
    payload: dict[str, Any] = {
        "domain": domain,
        "position_id": position_id,
        "apply_url": apply_page_url(position_id),
        "job": {
            "id": job_detail.get("id"),
            "name": job_detail.get("name"),
            "department": job_detail.get("department"),
            "location": job_detail.get("location"),
            "display_job_id": job_detail.get("display_job_id"),
        },
        "candidate": candidate,
        "answers": answers,
        "questions": questions,
        "submit": {
            "domain": domain,
            "pids": position_id,
            "candidate": candidate,
            "answers": answers,
        },
    }

    resume_meta = resume_meta_for_payload(resume_file)
    if resume_meta is not None:
        payload["resume_file"] = resume_meta
    if include_resume_bytes and resume_file is not None:
        payload["resume_upload"] = {
            "domain": domain,
            "resume_file_name": resume_file.filename,
            "resume_content": base64.b64encode(resume_file.data).decode("ascii"),
        }
    return payload


def build_submit_body(
    *,
    domain: str,
    position_id: str,
    candidate: dict[str, Any],
    answers: dict[str, Any],
) -> dict[str, Any]:
    """Body for POST /api/application/v2/submit."""
    return {
        "domain": domain,
        "pids": position_id,
        "candidate": candidate,
        "answers": answers,
    }


def build_resume_upload_body(
    *,
    domain: str,
    resume_file: ResumeFile,
) -> dict[str, Any]:
    """Body for POST /api/pcsx/upload_resume."""
    return {
        "domain": domain,
        "resume_file_name": resume_file.filename,
        "resume_content": base64.b64encode(resume_file.data).decode("ascii"),
    }


def _cover_letter_text(
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
) -> str:
    if cover_letter and cover_letter.strip():
        return cover_letter.strip()
    template = profile.cover_letter_template.strip()
    if template:
        return render_cover_letter(template, company=company, job_title=job_title)
    return profile.resume_text.strip()


def _location_detail(location: str) -> dict[str, str]:
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if len(parts) >= 3:
        return {"city": parts[0], "state": parts[1], "country": parts[2]}
    if len(parts) == 2:
        return {"city": parts[0], "state": parts[1]}
    if len(parts) == 1:
        return {"city": parts[0]}
    return {}


def _question_sections(questions: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    default = questions.get("default")
    if isinstance(default, dict) and isinstance(default.get("fields"), list):
        sections.extend(item for item in default["fields"] if isinstance(item, dict))
    fields = questions.get("fields")
    if isinstance(fields, list):
        sections.extend(item for item in fields if isinstance(item, dict))
    return sections
