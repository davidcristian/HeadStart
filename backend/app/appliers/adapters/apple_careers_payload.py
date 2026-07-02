"""Apple Careers apply payload builders."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.apple_careers_common import (
    TRIGGER_SELF_SUBMIT,
    apply_job_url,
    apply_page_url,
    questionnaire_url,
    upload_resume_url,
)
from app.appliers.adapters.apple_careers_detail import AppleCareersJobDetail
from app.appliers.adapters.greenhouse import split_name
from app.appliers.resume import resume_meta_for_payload
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile


def build_contact(
    profile: ProfileData | ApplyProfile,
) -> dict[str, Any]:
    """Map application profile fields to Apple Careers contact JSON."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")
    contact: dict[str, Any] = {
        "firstName": first_name,
        "lastName": last_name,
        "preferredEmail": email,
    }
    phone = profile.phone.strip()
    if phone:
        contact["preferredPhone"] = phone
    return contact


def build_links(profile: ProfileData | ApplyProfile) -> list[dict[str, str]]:
    """External profile links for the Apple talent payload."""
    links: list[dict[str, str]] = []
    linkedin = profile.links.linkedin.strip()
    if linkedin:
        links.append({"type": "linkedin", "url": linkedin})
    github = profile.links.github.strip()
    if github:
        links.append({"type": "github", "url": github})
    website = profile.links.website.strip()
    if website:
        links.append({"type": "website", "url": website})
    return links


def build_employments(profile: ProfileData | ApplyProfile) -> list[dict[str, Any]]:
    """Map structured work experience rows to Apple employments."""
    employments: list[dict[str, Any]] = []
    for row in profile.work_experience:
        title = row.job_title.strip()
        company = row.company.strip()
        if not title and not company:
            continue
        entry: dict[str, Any] = {
            "jobTitle": title,
            "employerName": company,
            "isCurrent": row.is_current,
        }
        location = row.location.strip()
        if location:
            entry["location"] = location
        if row.start_year is not None:
            entry["startYear"] = row.start_year
        if row.start_month is not None:
            entry["startMonth"] = row.start_month
        if row.end_year is not None:
            entry["endYear"] = row.end_year
        if row.end_month is not None:
            entry["endMonth"] = row.end_month
        description = row.description.strip()
        if description:
            entry["description"] = description
        employments.append(entry)
    return employments


def build_education_degrees(profile: ProfileData | ApplyProfile) -> list[dict[str, Any]]:
    """Map structured education rows to Apple educationDegrees."""
    degrees: list[dict[str, Any]] = []
    for row in profile.education:
        school = row.school.strip()
        if not school:
            continue
        entry: dict[str, Any] = {"schoolName": school}
        degree = row.degree.strip()
        if degree:
            entry["degreeName"] = degree
        field = row.field_of_study.strip()
        if field:
            entry["fieldOfStudy"] = field
        if row.start_year is not None:
            entry["startYear"] = row.start_year
        if row.end_year is not None:
            entry["endYear"] = row.end_year
        gpa = row.gpa.strip()
        if gpa:
            entry["gpa"] = gpa
        degrees.append(entry)
    return degrees


def build_roles(
    detail: AppleCareersJobDetail,
    *,
    talent_id: str,
    post_locations: list[dict[str, Any]],
    resume_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Roles object sent to applyJob."""
    roles: dict[str, Any] = {
        "talentID": talent_id,
        "positionID": detail.position_id,
        "submitted": True,
        "pipelineType": detail.pipeline_type,
    }
    if detail.role_location_selection:
        roles["resubmitted"] = True
        roles["roleLocation"] = len(post_locations) > 0
        roles["storeLocations"] = post_locations
    else:
        roles["postLocations"] = post_locations
    if resume_ref:
        roles["resume"] = resume_ref
    return roles


def build_talent(
    profile: ProfileData | ApplyProfile,
    *,
    talent_id: str,
    contact: dict[str, Any],
) -> dict[str, Any]:
    """Talent profile object sent with applyJob."""
    talent: dict[str, Any] = {
        "talentId": talent_id,
        "contact": contact,
        "submittedFlow": True,
        "profileUpdateSelection": "MANUAL",
    }
    links = build_links(profile)
    if links:
        talent["links"] = links
    employments = build_employments(profile)
    if employments:
        talent["employments"] = employments
        talent["employmentHasAtLeastOneJob"] = True
    education = build_education_degrees(profile)
    if education:
        talent["educationDegrees"] = education
    skills = [skill.strip() for skill in profile.skills if skill.strip()]
    if skills:
        talent["skills"] = skills
    languages = [
        {
            "language": row.language.strip(),
            "proficiency": row.proficiency.strip(),
            "isNative": row.is_native,
        }
        for row in profile.languages
        if row.language.strip()
    ]
    if languages:
        talent["languages"] = languages
    return talent


def build_apply_body(
    *,
    detail: AppleCareersJobDetail,
    talent_id: str,
    talent: dict[str, Any],
    roles: dict[str, Any],
    questionnaire_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Body for PUT /talent/:talentId/applyJob."""
    body: dict[str, Any] = {
        "roles": roles,
        "talent": talent,
        "triggerType": TRIGGER_SELF_SUBMIT,
    }
    if questionnaire_answers:
        body["questionnaireAnswers"] = questionnaire_answers
    if detail.managed_pipeline_role:
        body["boardId"] = detail.position_id
    return body


def resolve_post_locations(
    detail: AppleCareersJobDetail,
    config: dict[str, Any],
    profile: ProfileData | ApplyProfile,
) -> list[dict[str, Any]]:
    """Selected post/store locations for the apply roles payload."""
    configured = config.get("post_locations") or config.get("store_locations")
    if isinstance(configured, list) and configured:
        return [item for item in configured if isinstance(item, dict)]
    if detail.locations:
        return [dict(location) for location in detail.locations]
    return []


def build_application_payload(
    *,
    detail: AppleCareersJobDetail,
    profile: ProfileData | ApplyProfile,
    talent_id: str | None,
    post_locations: list[dict[str, Any]],
    contact: dict[str, Any],
    talent: dict[str, Any],
    roles: dict[str, Any],
    apply_body: dict[str, Any],
    resume_file: ResumeFile | None,
    questionnaire: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preview payload for dry-run and live submit orchestration."""
    payload: dict[str, Any] = {
        "position_id": detail.position_id,
        "job_number": detail.job_number,
        "job_type": detail.job_type,
        "apply_url": apply_page_url(detail.locale, detail.position_id),
        "job": {
            "title": detail.title,
            "pipeline_type": detail.pipeline_type,
            "role_location_selection": detail.role_location_selection,
            "managed_pipeline_role": detail.managed_pipeline_role,
            "locations": list(detail.locations),
        },
        "post_locations": post_locations,
        "contact": contact,
        "talent": talent,
        "roles": roles,
        "apply_job": {
            "method": "PUT",
            "url": apply_job_url(talent_id) if talent_id else None,
            "body": apply_body,
        },
        "questionnaire_url": questionnaire_url(detail.position_id),
    }
    if questionnaire is not None:
        payload["questionnaire"] = questionnaire
    if resume_file is not None:
        payload["resume_file"] = resume_meta_for_payload(resume_file)
        if talent_id:
            payload["resume_upload"] = {
                "method": "POST",
                "url": upload_resume_url(talent_id),
            }
    return payload


def build_resume_ref(upload_response: Any) -> dict[str, Any] | None:
    """Map an uploadFile response into the roles.resume reference object."""
    if not isinstance(upload_response, dict):
        return None
    file_id = upload_response.get("fileId") or upload_response.get("id")
    if file_id is None:
        return None
    resume: dict[str, Any] = {"fileId": file_id}
    for key in ("pdfFileId", "bucketId", "pdfBucketId"):
        value = upload_response.get(key)
        if value is not None:
            resume[key] = value
    return resume
