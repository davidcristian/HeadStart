"""LinkedIn-hosted Easy Apply payload helpers."""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.appliers.adapters.greenhouse import split_name
from app.appliers.adapters.linkedin_detail import LinkedInJobDetail
from app.appliers.adapters.linkedin_easy_apply_form import (
    element_title,
    is_file_upload_element,
    iter_form_elements,
)
from app.appliers.resume import resume_meta_for_payload
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile

SUBMIT_URL = (
    "https://www.linkedin.com/voyager/api/voyagerJobsDashOnsiteApplyApplication"
    "?action=submitApplication"
)
_FIELD_LABEL_RE = re.compile(r"[^a-z0-9]+")


def build_easy_apply_payload(
    detail: LinkedInJobDetail,
    profile: ProfileData | ApplyProfile,
    *,
    company: str,
    job_title: str,
    cover_letter: str | None,
    resume_file: ResumeFile | None,
    form_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map profile data to a LinkedIn Easy Apply preview payload."""
    if resume_file is None and isinstance(profile, ApplyProfile):
        resume_file = profile.resume_file
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not email:
        raise ValueError("profile full_name and email are required to apply on LinkedIn")

    payload: dict[str, Any] = {
        "route": "linkedin_hosted",
        "jobId": detail.job_id,
        "jobPostingUrn": f"urn:li:fsd_jobPosting:{detail.job_id}",
        "referenceId": detail.reference_id,
        "trackingId": detail.tracking_id,
        "applicant": {
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
        },
        "submit_url": SUBMIT_URL,
    }
    phone = profile.phone.strip()
    if phone:
        payload["applicant"]["phone"] = phone
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
    if resume_text:
        payload["resumeText"] = resume_text
    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume_file"] = meta

    if form_payload is not None:
        payload["form"] = form_payload
        responses, missing = build_form_responses(form_payload, profile, cover_letter=letter)
        payload["responses"] = responses
        if missing:
            payload["missing_required_fields"] = missing

    for key, value in profile.answers.items():
        if value:
            payload.setdefault("answers", {})[key] = value

    return payload


def build_submit_body(
    payload: dict[str, Any],
    *,
    file_upload_responses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Body sent to Voyager on live Easy Apply submit."""
    responses = payload.get("responses")
    if not isinstance(responses, list) or not responses:
        raise ValueError(
            "linkedin live apply could not map required Easy Apply questions; "
            "preview with dry_run and add profile.answers for unmapped fields"
        )
    reference = payload.get("referenceId") or f"INITIAL_PAGE_LOAD::::{uuid.uuid4()}"
    uploads = list(file_upload_responses or payload.get("fileUploadResponses") or [])
    return {
        "followCompany": False,
        "referenceId": reference,
        "responses": responses,
        "trackingCode": payload.get("trackingId") or "TRK_INITIAL_PAGE_LOAD",
        "fileUploadResponses": uploads,
    }


def build_form_responses(
    form_payload: dict[str, Any],
    profile: ProfileData | ApplyProfile,
    *,
    cover_letter: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Best-effort mapping from Easy Apply form elements to profile fields."""
    responses: list[dict[str, Any]] = []
    missing: list[str] = []
    first_name, last_name = split_name(profile.full_name)
    for element in iter_form_elements(form_payload):
        urn = str(element.get("entityUrn") or element.get("urn") or "").strip()
        if not urn:
            continue
        if is_file_upload_element(element):
            continue
        title = element_title(element)
        label_key = _FIELD_LABEL_RE.sub("_", title.lower()).strip("_")
        required = bool(element.get("required"))
        value = _value_for_label(
            label_key,
            profile=profile,
            cover_letter=cover_letter,
            first_name=first_name,
            last_name=last_name,
        )
        if value is None:
            value = profile.answers.get(urn) or profile.answers.get(label_key)
        if value is None or str(value).strip() == "":
            if required:
                missing.append(title or urn)
            continue
        responses.append(
            {
                "formElementUrn": urn,
                "formElementInputValues": [_input_value_for_element(element, str(value).strip())],
            }
        )
    return responses, missing


def _value_for_label(
    label_key: str,
    *,
    profile: ProfileData | ApplyProfile,
    cover_letter: str | None,
    first_name: str,
    last_name: str,
) -> str | None:
    if "first_name" in label_key or label_key == "first":
        return first_name or None
    if "last_name" in label_key or label_key == "last":
        return last_name or None
    if "email" in label_key:
        return profile.email.strip() or None
    if "phone" in label_key or "mobile" in label_key:
        return profile.phone.strip() or None
    if "city" in label_key or "location" in label_key:
        return profile.location.strip() or None
    if "cover" in label_key:
        return cover_letter
    return None


def _input_value_for_element(element: dict[str, Any], value: str) -> dict[str, Any]:
    component = element.get("formComponentResolutionResult")
    if isinstance(component, dict):
        if "singleLineTextFormComponent" in component:
            return {"textInputValue": value}
        if "multilineTextFormComponent" in component:
            return {"textInputValue": value}
    return {"textInputValue": value}


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
