"""Payload builders for the iCIMS Talent Cloud Partner API apply adapter."""

from __future__ import annotations

from typing import Any

from app.appliers.resume import resume_meta_for_payload
from app.appliers.text import split_name
from app.schemas.profile import ProfileData, ResumeFile

# Default candidate folder from iCIMS docs examples ("Cand:Unreviewed").
_DEFAULT_FOLDER_ID = "D32006"
# Default applicant workflow status ("Recently Applied").
_DEFAULT_STATUS_ID = "D10100"
_DEFAULT_PHONE_TYPE_ID = "D83002"
_DEFAULT_ADDRESS_TYPE_ID = "D84002"


def build_person_payload(
    profile: ProfileData,
    *,
    config: dict[str, Any],
    cover_letter: str | None = None,
    resume_file: ResumeFile | None = None,
) -> dict[str, Any]:
    """Map an application profile to an iCIMS Person create JSON body."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    folder_id = str(config.get("folder_id") or _DEFAULT_FOLDER_ID).strip() or _DEFAULT_FOLDER_ID
    payload: dict[str, Any] = {
        "firstname": first_name,
        "lastname": last_name,
        "email": email,
        "folder": {"id": folder_id},
        "roles": {"candidate": True},
    }

    phone = profile.phone.strip()
    if phone:
        phone_type = str(config.get("phone_type_id") or _DEFAULT_PHONE_TYPE_ID).strip()
        payload["phones"] = [
            {
                "phonetype": {"id": phone_type or _DEFAULT_PHONE_TYPE_ID},
                "phonenumber": phone,
            }
        ]

    location = profile.location.strip()
    if location:
        address_type = str(config.get("address_type_id") or _DEFAULT_ADDRESS_TYPE_ID).strip()
        address: dict[str, Any] = {
            "addresstype": {"id": address_type or _DEFAULT_ADDRESS_TYPE_ID},
            "addressstreet1": location,
        }
        country_id = str(config.get("address_country_id") or "").strip()
        if country_id:
            address["addresscountry"] = {"id": country_id}
        city = str(profile.answers.get("address_city") or config.get("address_city") or "").strip()
        if city:
            address["addresscity"] = city
        state_id = str(
            profile.answers.get("address_state_id") or config.get("address_state_id") or ""
        ).strip()
        if state_id:
            address["addressstate"] = {"id": state_id}
        payload["addresses"] = [address]

    notes = _notes(profile, cover_letter=cover_letter, config=config)
    if notes:
        notes_field = str(config.get("notes_field") or "overview").strip() or "overview"
        payload[notes_field] = notes

    if resume_file is not None:
        meta = resume_meta_for_payload(resume_file)
        assert meta is not None
        payload["resume"] = meta

    # Pass-through custom field answers: profile.answers["icims_field1234"] → field1234
    for key, value in profile.answers.items():
        if not key.startswith("icims_"):
            continue
        field = key.removeprefix("icims_").strip()
        if field and value is not None and str(value).strip():
            payload[field] = value

    return payload


def build_workflow_payload(
    *,
    job_id: str,
    person_id: str | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build an applicantworkflows create body linking a person to a job."""
    status_id = str(config.get("status_id") or _DEFAULT_STATUS_ID).strip() or _DEFAULT_STATUS_ID
    source = str(config.get("application_source") or "HeadStart").strip() or "HeadStart"
    payload: dict[str, Any] = {
        "baseprofile": int(job_id) if job_id.isdigit() else job_id,
        "status": {"id": status_id},
        "source": source,
    }
    if person_id is not None:
        payload["associatedprofile"] = int(person_id) if person_id.isdigit() else person_id
    return payload


def build_dry_run_payload(
    *,
    person: dict[str, Any],
    workflow: dict[str, Any],
    customer_id: str | None,
    job_id: str,
    careers_base_url: str | None,
    apply_url: str | None,
    job_detail: dict[str, Any] | None,
) -> dict[str, Any]:
    """Preview envelope shown for dry-run (no Partner API calls)."""
    return {
        "customer_id": customer_id,
        "job_id": job_id,
        "careers_base_url": careers_base_url,
        "apply_url": apply_url,
        "person": person,
        "applicantworkflow": workflow,
        "job": _job_preview(job_detail) if job_detail else None,
        "live_submit": {
            "people": (
                f"POST https://api.icims.com/customers/{customer_id}/people"
                if customer_id
                else "POST https://api.icims.com/customers/<customer_id>/people"
            ),
            "applicantworkflows": (
                f"POST https://api.icims.com/customers/{customer_id}/applicantworkflows"
                if customer_id
                else "POST https://api.icims.com/customers/<customer_id>/applicantworkflows"
            ),
            "auth": "HTTP Basic (Partner Program credentials)",
        },
    }


def _notes(
    profile: ProfileData,
    *,
    cover_letter: str | None,
    config: dict[str, Any],
) -> str:
    if cover_letter and cover_letter.strip():
        return cover_letter.strip()
    template = profile.cover_letter_template.strip()
    if template:
        return template
    extra = str(config.get("notes") or profile.answers.get("notes") or "").strip()
    return extra


def _job_preview(job_detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": job_detail.get("slug") or job_detail.get("req_id"),
        "title": job_detail.get("title"),
        "hiring_organization": job_detail.get("hiring_organization"),
        "apply_url": job_detail.get("apply_url"),
        "full_location": job_detail.get("full_location") or job_detail.get("short_location"),
    }
