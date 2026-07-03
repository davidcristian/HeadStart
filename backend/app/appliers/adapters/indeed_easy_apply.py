"""Indeed-hosted Easy Apply payload helpers."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.indeed_detail import IndeedJobDetail
from app.appliers.resume import indeed_resume_file_fields, resume_meta_for_payload
from app.appliers.text import split_name
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile

SMARTAPPLY_SUBMIT_URL = "https://smartapply.indeed.com/beta/indeedapply/v2/applications"


def build_smartapply_url(detail: IndeedJobDetail) -> str:
    """Public smartapply entry URL for an Indeed-hosted Easy Apply job."""
    if detail.indeed_applyable_job_id:
        return (
            "https://smartapply.indeed.com/beta/indeedapply/applybyapplyablejobid"
            f"?indeedApplyableJobId={detail.indeed_applyable_job_id}"
        )
    return (
        "https://smartapply.indeed.com/beta/indeedapply/applybyapplyablejobid"
        f"?jk={detail.job_key}"
    )


def build_easy_apply_payload(
    detail: IndeedJobDetail,
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
    resume_file: ResumeFile | None,
) -> dict[str, Any]:
    """Map profile data to the Indeed-hosted Easy Apply JSON shape."""
    if resume_file is None and isinstance(profile, ApplyProfile):
        resume_file = profile.resume_file
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not email:
        raise ValueError("profile full_name and email are required to apply on Indeed")

    payload: dict[str, Any] = {
        "route": "indeed_hosted",
        "jobKey": detail.job_key,
        "smartapply_url": build_smartapply_url(detail),
        "applicant": {
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
        },
    }
    if detail.indeed_applyable_job_id:
        payload["indeedApplyableJobId"] = detail.indeed_applyable_job_id
    if detail.apply_continue_url:
        payload["continueUrl"] = detail.apply_continue_url

    phone = profile.phone.strip()
    if phone:
        payload["applicant"]["phoneNumber"] = phone

    location = profile.location.strip()
    if location:
        payload["applicant"]["location"] = location

    letter = _cover_letter_text(
        profile,
        company=company,
        job_title=job_title,
        cover_letter=cover_letter,
    )
    if letter:
        payload["coverLetter"] = letter

    resume_text = profile.resume_text.strip()
    if resume_text and resume_file is None:
        payload["resumeText"] = resume_text

    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume_file"] = meta

    for key, value in profile.answers.items():
        if value:
            payload.setdefault("answers", {})[key] = value

    return payload


def build_submit_body(
    payload: dict[str, Any],
    *,
    resume_file: ResumeFile | None = None,
) -> dict[str, Any]:
    """Body sent to smartapply on live submit (strips preview-only keys)."""
    applicant = dict(payload["applicant"])
    if resume_file is not None:
        applicant["resume"] = {"file": indeed_resume_file_fields(resume_file)}
    body = {
        "jobKey": payload["jobKey"],
        "applicant": applicant,
    }
    for optional in ("indeedApplyableJobId", "coverLetter", "answers"):
        if optional in payload:
            body[optional] = payload[optional]
    if resume_file is None and "resumeText" in payload:
        body["resumeText"] = payload["resumeText"]
    return body


def has_indeed_session_cookies(credentials: dict[str, dict[str, str]] | None) -> bool:
    """True when credential cookies look like a logged-in Indeed account."""
    if not credentials:
        return False
    cookies = credentials.get("cookies") or {}
    markers = ("PPID", "INDEED_CSRF_TOKEN", "SHOE", "SOCK", "CTK")
    return any(cookies.get(name) for name in markers)


def _cover_letter_text(
    profile: ProfileData,
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
    return (
        template.replace("{company}", company)
        .replace("{job_title}", job_title)
        .replace("{title}", job_title)
    )
