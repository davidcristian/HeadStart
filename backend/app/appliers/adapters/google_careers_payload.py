"""Google Careers apply payload builders."""

from __future__ import annotations

from typing import Any

from app.appliers.adapters.google_careers_detail import GoogleCareersJobDetail
from app.appliers.adapters.greenhouse import render_cover_letter, split_name
from app.appliers.resume import resume_meta_for_payload
from app.schemas.profile import ApplyProfile, ProfileData


def build_careers_profile(profile: ProfileData | ApplyProfile) -> dict[str, Any]:
    """Map HeadStart profile fields to a Google Careers profile object."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    careers_profile: dict[str, Any] = {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
    }
    phone = profile.phone.strip()
    if phone:
        careers_profile["phone"] = phone
    location = profile.location.strip()
    if location:
        careers_profile["location"] = location

    links = profile.links
    if links.linkedin.strip():
        careers_profile["linkedInUrl"] = links.linkedin.strip()
    if links.github.strip():
        careers_profile["githubUrl"] = links.github.strip()
    if links.website.strip():
        careers_profile["websiteUrl"] = links.website.strip()

    resume_text = profile.resume_text.strip()
    if resume_text:
        careers_profile["resumeText"] = resume_text

    if profile.answers:
        careers_profile["answers"] = dict(profile.answers)
    return careers_profile


def build_save_profile_args(careers_profile: dict[str, Any]) -> list[Any]:
    """Best-effort args envelope for CPortalUiService.SaveCareersProfile."""
    return [careers_profile]


def build_create_packet_args(detail: GoogleCareersJobDetail) -> list[Any]:
    """Best-effort args envelope for CPortalUiService.CreatePacket."""
    packet: dict[str, Any] = {
        "jobId": detail.apply_job_id,
        "listingId": detail.external_id,
        "title": detail.title,
        "company": detail.company,
    }
    if detail.company_resource:
        packet["companyResource"] = detail.company_resource
    if detail.location_code:
        packet["locationCode"] = detail.location_code
    return [packet]


def build_save_packet_args(
    packet_id: str,
    *,
    careers_profile: dict[str, Any],
    cover_letter: str | None,
    job_title: str,
    company: str,
    profile: ProfileData | ApplyProfile,
) -> list[Any]:
    """Best-effort args envelope for CPortalUiService.SavePacket."""
    answers = dict(careers_profile.get("answers") or {})
    letter = (cover_letter or "").strip()
    if not letter:
        template = profile.cover_letter_template.strip()
        if template:
            letter = render_cover_letter(template, company=company, job_title=job_title)
    if letter:
        answers["coverLetter"] = letter

    packet_body: dict[str, Any] = {
        "packetId": packet_id,
        "profile": careers_profile,
    }
    if answers:
        packet_body["answers"] = answers
    return [packet_body, 1, 0]


def build_submit_packet_args(packet_id: str) -> list[Any]:
    """Best-effort args envelope for CPortalUiService.SubmitPacket."""
    return [{"packetId": packet_id}, 1, 0]


def build_application_payload(
    detail: GoogleCareersJobDetail,
    profile: ProfileData | ApplyProfile,
    *,
    job_title: str,
    company: str,
    cover_letter: str | None = None,
    resume_file: Any = None,
    include_rpc_steps: bool = False,
) -> dict[str, Any]:
    """Assemble the preview payload returned by dry-run apply."""
    careers_profile = build_careers_profile(profile)
    payload: dict[str, Any] = {
        "apply_job_id": detail.apply_job_id,
        "apply_url": detail.apply_url,
        "listing_id": detail.external_id,
        "title": detail.title,
        "company": detail.company,
        "company_resource": detail.company_resource,
        "location_code": detail.location_code,
        "location_label": detail.location_label,
        "careers_profile": careers_profile,
    }

    letter = (cover_letter or "").strip()
    if not letter:
        template = profile.cover_letter_template.strip()
        if template:
            letter = render_cover_letter(template, company=company, job_title=job_title)
    if letter:
        payload["cover_letter"] = letter

    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume_file"] = meta

    if include_rpc_steps:
        payload["rpc_steps"] = [
            {"rpc_id": "qvYBjf", "args": build_save_profile_args(careers_profile)},
            {"rpc_id": "tBY1Qe", "args": build_create_packet_args(detail)},
            {"rpc_id": "o6YK3", "args": "<packet_id from create>"},
            {"rpc_id": "pmtdJd", "args": "<packet_id from create>"},
        ]
    return payload


def extract_packet_id(create_result: Any) -> str | None:
    """Pull a packet id from a CreatePacket RPC result."""
    if isinstance(create_result, dict):
        for key in ("packetId", "id", "applicationId"):
            value = create_result.get(key)
            if value:
                return str(value)
    if isinstance(create_result, list) and create_result:
        head = create_result[0]
        if isinstance(head, str) and head:
            return head
        if isinstance(head, dict):
            for key in ("packetId", "id", "applicationId"):
                value = head.get(key)
                if value:
                    return str(value)
    return None


def extract_application_id(submit_result: Any) -> str | None:
    """Pull an application id from a SubmitPacket RPC result."""
    if isinstance(submit_result, dict):
        for key in ("applicationId", "id", "packetId"):
            value = submit_result.get(key)
            if value:
                return str(value)
    if isinstance(submit_result, list) and submit_result:
        head = submit_result[0]
        if isinstance(head, str) and head:
            return head
        if isinstance(head, dict):
            for key in ("applicationId", "id", "packetId"):
                value = head.get(key)
                if value:
                    return str(value)
    return None
