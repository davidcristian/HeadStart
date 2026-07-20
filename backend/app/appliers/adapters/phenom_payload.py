"""Partner Apply API payload builders for Phenom-hosted applications."""

from __future__ import annotations

import base64
from typing import Any

from app.appliers.adapters.phenom_detail import PhenomJobDetail
from app.appliers.text import split_name
from app.schemas.profile import ProfileData, ResumeFile


def build_application_payload(
    profile: ProfileData,
    *,
    job_id: str,
    applicant_source: str = "HeadStart",
    resume_file: ResumeFile | None = None,
    include_resume_bytes: bool = False,
    custom_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map profile fields onto Phenom ``POST /apply/v2/applications`` JSON."""
    first_name, last_name = split_name(profile.full_name)
    if not first_name or not profile.email.strip():
        raise ValueError("profile full_name and email are required to apply via Phenom")

    candidate: dict[str, Any] = {
        "firstName": first_name[:20],
        "lastName": (last_name or first_name)[:20],
        "contactData": {"email": profile.email.strip()[:50]},
    }
    phone = profile.phone.strip()
    if phone:
        candidate["contactData"]["phoneNumber"] = phone
    location = profile.location.strip()
    if location:
        candidate["addressData"] = {"addressLine1": location}

    experience = _experience_data(profile)
    if experience:
        candidate["experienceData"] = experience

    body: dict[str, Any] = {
        "candidateData": candidate,
        "jobApplicationData": {
            "jobId": job_id[:50],
            "applicantSource": applicant_source[:100] or "HeadStart",
        },
    }
    if custom_fields:
        body["customFieldData"] = custom_fields

    if resume_file is not None:
        if include_resume_bytes:
            body["resumeData"] = {
                "fileContent": base64.b64encode(resume_file.data).decode("ascii"),
                "fileName": resume_file.filename,
                "contentTypeId": resume_file.content_type,
            }
        else:
            body["resumeData"] = {
                "fileName": resume_file.filename,
                "contentTypeId": resume_file.content_type,
                "size_bytes": resume_file.size_bytes,
            }
    return body


def build_dry_run_payload(
    *,
    application: dict[str, Any],
    detail: PhenomJobDetail,
    careers_base_url: str | None,
    route: str,
) -> dict[str, Any]:
    """Envelope returned for dry-run / error payloads."""
    return {
        "phenom_route": route,
        "job_id": detail.job_id,
        "title": detail.title or None,
        "apply_url": detail.apply_url,
        "external_apply": detail.external_apply,
        "ref_num": detail.ref_num or None,
        "careers_base_url": careers_base_url,
        "application": application,
    }


def custom_fields_from_answers(answers: dict[str, str]) -> dict[str, Any]:
    """Map ``phenom_<field>`` profile answers into Apply API customFieldData."""
    out: dict[str, Any] = {}
    for key, value in answers.items():
        if not key.startswith("phenom_"):
            continue
        field = key[len("phenom_") :].strip()
        if field and str(value).strip():
            out[field] = str(value).strip()
    return out


def _experience_data(profile: ProfileData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in profile.work_experience:
        company = entry.company.strip()
        title = entry.job_title.strip()
        if not company or not title:
            continue
        row: dict[str, Any] = {"companyName": company, "title": title}
        if entry.location.strip():
            row["location"] = entry.location.strip()
        if entry.description.strip():
            row["description"] = entry.description.strip()[:2000]
        from_to: dict[str, Any] = {"format": "MM-yyyy"}
        if entry.start_month and entry.start_year:
            from_to["startDate"] = f"{entry.start_month:02d}-{entry.start_year}"
        elif entry.start_year:
            from_to["format"] = "yyyy"
            from_to["startDate"] = str(entry.start_year)
        else:
            continue
        if entry.is_current:
            from_to["currentlyWorkHere"] = "true"
        elif entry.end_month and entry.end_year:
            from_to["endDate"] = f"{entry.end_month:02d}-{entry.end_year}"
        elif entry.end_year:
            from_to["format"] = "yyyy"
            from_to["endDate"] = str(entry.end_year)
        row["fromTo"] = from_to
        rows.append(row)
    return rows
