"""Amazon Jobs applicant/application payload builders."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.amazon_jobs_common import (
    applicant_update_url,
    draft_application_url,
    get_application_url,
    submit_application_url,
)
from app.appliers.adapters.amazon_jobs_detail import AmazonJobDetail
from app.appliers.resume import resume_meta_for_payload
from app.appliers.text import render_cover_letter, split_name
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile


def build_applicant_body(
    profile: ProfileData | ApplyProfile,
    *,
    cover_letter: str | None = None,
    company: str,
    job_title: str,
) -> dict[str, Any]:
    """Map application profile fields to amazon.jobs applicant JSON."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name:
        raise ValueError("profile full_name is required to apply")
    if not email:
        raise ValueError("profile email is required to apply")

    applicant: dict[str, Any] = {
        "legal_first_name": first_name,
        "legal_last_name": last_name or first_name,
        "email": email,
    }

    phone = profile.phone.strip()
    if phone:
        applicant["primary_phone_number"] = phone
        applicant["phone_number"] = phone

    location = profile.location.strip()
    if location:
        applicant["location"] = location

    linkedin = profile.links.linkedin.strip()
    if linkedin:
        applicant["linkedin_url"] = linkedin

    cover = _cover_letter_text(
        profile,
        company=company,
        job_title=job_title,
        cover_letter=cover_letter,
    )
    if cover:
        applicant["cover_letter"] = cover

    for key, value in profile.answers.items():
        if value:
            applicant[key] = value

    return {"applicant": applicant}


def build_application_payload(
    detail: AmazonJobDetail,
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None = None,
    resume_file: ResumeFile | None = None,
    recruiting_source: str | None = None,
) -> dict[str, Any]:
    """Preview payload for dry-run: applicant sync + draft + submit steps."""
    applicant_body = build_applicant_body(
        profile,
        cover_letter=cover_letter,
        company=company,
        job_title=job_title,
    )
    draft_body: dict[str, Any] = {}
    if recruiting_source:
        draft_body["recruiting_source"] = recruiting_source

    payload: dict[str, Any] = {
        "job": {
            "job_id": detail.job_id,
            "title": detail.title or job_title,
            "company": detail.company or company,
            "location": detail.location,
            "country_code": detail.country_code,
            "apply_url": detail.apply_url,
            "account_apply_url": detail.account_apply_url,
        },
        "applicant_update": {
            "url": applicant_update_url(),
            "body": applicant_body,
        },
        "draft_application": {
            "url": draft_application_url(detail.job_id),
            "body": draft_body,
        },
        "submit_application": {
            "url": submit_application_url(detail.job_id),
            "body": {},
        },
        "get_application": {
            "url": get_application_url(detail.job_id),
        },
    }

    resume_meta = resume_meta_for_payload(resume_file)
    if resume_meta is not None:
        payload["resume_upload"] = {
            "filename": resume_meta["filename"],
            "content_type": resume_meta["content_type"],
            "size_bytes": resume_meta["size_bytes"],
        }

    return payload


def _cover_letter_text(
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
) -> str | None:
    if cover_letter and cover_letter.strip():
        return cover_letter.strip()
    template = profile.cover_letter_template.strip()
    if not template:
        return None
    return render_cover_letter(template, company=company, job_title=job_title)
