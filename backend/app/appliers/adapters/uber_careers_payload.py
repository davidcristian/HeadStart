"""Uber Careers applicationFormRequest payload builders."""

from __future__ import annotations

import base64
from typing import Any

from app.appliers.adapters.uber_careers_common import (
    _SOURCE_ORIGIN,
    yes_no_answer,
)
from app.appliers.adapters.uber_careers_questions import (
    build_question_responses,
    normalize_question,
)
from app.appliers.resume import resume_meta_for_payload
from app.appliers.structured_profile import applicable_education, applicable_work_experience
from app.appliers.text import split_name
from app.schemas.profile import ProfileData, ResumeFile


def build_application_form_request(
    profile: ProfileData,
    *,
    job_id: int,
    job_title: str,
    session_token: str | None,
    additional_questions: list[dict[str, Any]],
    resume_file: ResumeFile | None,
    include_resume_bytes: bool,
) -> dict[str, Any]:
    """Map application profile data to Uber's ApplicationFormRequestInput shape."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name:
        raise ValueError("profile full_name is required to apply")
    if not email:
        raise ValueError("profile email is required to apply")

    phone = build_phone_number(profile)
    answers = profile.answers
    request: dict[str, Any] = {
        "firstName": first_name,
        "lastName": last_name or first_name,
        "emailAddress": email,
        "phoneNumber": phone,
        "jobID": job_id,
        "jobTitle": job_title,
        "sourceOrigin": _SOURCE_ORIGIN,
        "sourceDevice": str(answers.get("source_device") or "Desktop"),
        "joveoClickID": str(answers.get("joveo_click_id") or ""),
        "sessionToken": session_token or "",
        "linkedInURL": profile.links.linkedin.strip(),
        "githubURL": profile.links.github.strip(),
        "otherURL": profile.links.website.strip(),
        "legalRightToWork": yes_no_answer(answers, "legal_right_to_work"),
        "inUSA": yes_no_answer(answers, "in_usa"),
        "requireVisaSponsorship": yes_no_answer(answers, "require_visa_sponsorship"),
        "sex": str(answers.get("gender") or answers.get("sex") or "").strip(),
        "sexualOrientation": str(answers.get("sexual_orientation") or "").strip(),
        "disability": str(answers.get("disability") or "").strip(),
        "veteran": str(answers.get("veteran") or "").strip(),
        "race": str(answers.get("race") or "").strip(),
        "driverPartnerQuestion": yes_no_answer(answers, "driver_partner_question") == "Yes",
        "openForRoles": yes_no_answer(answers, "open_for_roles") == "Yes",
        "subsidiaryQuestion": str(answers.get("subsidiary_question") or "").strip(),
        "attachments": build_attachments(resume_file, include_bytes=include_resume_bytes),
        "positions": build_positions(profile),
        "educations": build_educations(profile),
        "additionalQuestionsResponses": build_question_responses(
            additional_questions,
            answers,
        ),
    }

    arbitration = answers.get("arbitration_agreement")
    if arbitration:
        request["arbitrationAgreement"] = (
            yes_no_answer(
                answers,
                "arbitration_agreement",
            )
            == "Yes"
        )
    data_retention = answers.get("data_retention_question")
    if data_retention:
        request["dataRetentionQuestion"] = (
            yes_no_answer(
                answers,
                "data_retention_question",
            )
            == "Yes"
        )

    return request


def build_application_payload(
    profile: ProfileData,
    *,
    job_id: int,
    job_title: str,
    company: str,
    additional_questions: list[dict[str, Any]],
    resume_file: ResumeFile | None,
    cover_letter: str | None,
) -> dict[str, Any]:
    """Dry-run preview payload with metadata and redacted secrets/bytes.

    Never embeds a live ``sessionToken`` because ApplicationLog persists this
    payload.
    """
    application_form_request = build_application_form_request(
        profile,
        job_id=job_id,
        job_title=job_title,
        session_token=None,
        additional_questions=additional_questions,
        resume_file=resume_file,
        include_resume_bytes=False,
    )
    payload: dict[str, Any] = {
        "job_id": job_id,
        "company": company,
        "application_form_request": application_form_request,
        "resume_file": resume_meta_for_payload(resume_file),
        "additional_questions": [normalize_question(row) for row in additional_questions],
    }
    if cover_letter and cover_letter.strip():
        payload["cover_letter_preview"] = cover_letter.strip()
    return payload


def build_phone_number(profile: ProfileData) -> dict[str, str]:
    """Map profile phone fields to Uber's phoneNumber object."""
    answers = profile.answers
    country_code = str(
        answers.get("phone_country_code") or answers.get("country_code") or ""
    ).strip()
    number = str(answers.get("phone_number") or "").strip()
    if not number:
        number = profile.phone.strip()
    if number.startswith("+"):
        digits = "".join(ch for ch in number if ch.isdigit())
        if not country_code:
            if digits.startswith("1") and len(digits) == 11:
                country_code = "1"
                number = digits[1:]
            elif len(digits) > 10:
                country_code = digits[:-10]
                number = digits[-10:]
            else:
                country_code = "1"
                number = digits[1:] if digits.startswith("1") and len(digits) > 1 else digits
    if not country_code:
        country_code = "1"
    cleaned = "".join(ch for ch in number if ch.isdigit())
    return {"countryCode": country_code, "number": cleaned or number}


def build_attachments(
    resume_file: ResumeFile | None,
    *,
    include_bytes: bool,
) -> list[dict[str, str]]:
    """Resume attachment list for Uber's application form."""
    if resume_file is None:
        return []
    if not include_bytes:
        return [{"name": resume_file.filename, "content": "<redacted>"}]
    return [
        {
            "name": resume_file.filename,
            "content": base64.b64encode(resume_file.data).decode("ascii"),
        }
    ]


def build_positions(profile: ProfileData) -> list[dict[str, Any]]:
    """Map structured work experience to Uber positions entries."""
    positions: list[dict[str, Any]] = []
    for entry in applicable_work_experience(profile):
        position: dict[str, Any] = {
            "title": entry.job_title.strip(),
            "companyName": entry.company.strip(),
            "description": entry.description.strip(),
            "isCurrent": entry.is_current,
            "startDate": _month_year(entry.start_month, entry.start_year),
            "endDate": _month_year(
                None if entry.is_current else entry.end_month,
                None if entry.is_current else entry.end_year,
            ),
        }
        positions.append(position)
    return positions


def build_educations(profile: ProfileData) -> list[dict[str, Any]]:
    """Map structured education rows to Uber educations entries."""
    educations: list[dict[str, Any]] = []
    for entry in applicable_education(profile):
        degree = entry.degree.strip()
        field = entry.field_of_study.strip()
        education: dict[str, Any] = {
            "schoolName": entry.school.strip(),
            "fieldOfStudy": field,
            "degree": degree,
            "startDate": _month_year(None, entry.start_year),
            "endDate": _month_year(None, entry.end_year),
        }
        educations.append(education)
    return educations


def _month_year(month: int | None, year: int | None) -> dict[str, str]:
    return {
        "month": str(month) if month else "",
        "year": str(year) if year else "",
    }
