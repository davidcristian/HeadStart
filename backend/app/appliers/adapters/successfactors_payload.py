"""Payload builders for the SuccessFactors OData Recruiting apply adapter."""

from __future__ import annotations

import base64
from typing import Any

from app.appliers.resume import resume_meta_for_payload
from app.appliers.text import split_name
from app.schemas.profile import ProfileData, ResumeFile

_LIVE_BLOCKER = (
    "Career Site Builder public apply (/talentcommunity/apply/) is login-gated "
    "with no unauthenticated candidate POST. Dry-run previews the OData payload; "
    "live submit needs Recruiting OData credentials "
    "(config.odata_base_url + company_id + API user Basic Auth)."
)


def build_candidate_payload(
    profile: ProfileData,
    *,
    country: str,
    agree_to_privacy: bool = True,
) -> dict[str, Any]:
    """Map an application profile to an OData ``Candidate`` create body."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")
    if not country.strip():
        raise ValueError("candidate country is required (config.country)")

    payload: dict[str, Any] = {
        "__metadata": {"type": "SFOData.Candidate"},
        "firstName": first_name,
        "lastName": last_name,
        "primaryEmail": email,
        "country": country.strip(),
        "agreeToPrivacyStatement": "true" if agree_to_privacy else "false",
    }
    phone = profile.phone.strip()
    if phone:
        payload["cellPhone"] = phone
    return payload


def build_attachment_payload(resume_file: ResumeFile) -> dict[str, Any]:
    """Map a stored resume to an OData ``Attachment`` create body."""
    return {
        "__metadata": {"type": "SFOData.Attachment"},
        "fileName": resume_file.filename,
        "module": "RECRUITING",
        "moduleCategory": "RESUME",
        "fileContent": base64.b64encode(resume_file.data).decode("ascii"),
    }


def build_application_payload(
    profile: ProfileData,
    *,
    job_req_id: str,
    candidate_id: str | None,
    cover_letter: str | None = None,
    attachment_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map profile + job to an OData ``JobApplication`` create body."""
    first_name, last_name = split_name(profile.full_name)
    email = profile.email.strip()
    if not first_name or not last_name:
        raise ValueError("profile full_name must include first and last name")
    if not email:
        raise ValueError("profile email is required to apply")

    payload: dict[str, Any] = {
        "__metadata": {"type": "SFOData.JobApplication"},
        "jobReqId": int(job_req_id) if job_req_id.isdigit() else job_req_id,
        "firstName": first_name,
        "lastName": last_name,
        "contactEmail": email,
    }
    if candidate_id:
        # OData navigation / key reference styles vary by tenant; include both.
        payload["candidateId"] = candidate_id
        payload["candidate"] = {"__metadata": {"uri": f"Candidate({candidate_id})"}}

    phone = profile.phone.strip()
    if phone:
        payload["cellPhone"] = phone

    if cover_letter and cover_letter.strip():
        payload["coverLetter"] = cover_letter.strip()

    if attachment_id:
        payload["resume"] = {"__metadata": {"uri": f"Attachment({attachment_id})"}}

    cfg = config or {}
    for key, value in profile.answers.items():
        if not key.startswith("sf_") or value is None:
            continue
        field = key[3:].strip()
        if field:
            payload[field] = value

    # Optional source/search config overrides for template fields.
    for key, value in cfg.items():
        if not isinstance(key, str) or not key.startswith("sf_field_"):
            continue
        field = key[len("sf_field_") :].strip()
        if field and value is not None:
            payload[field] = value

    return payload


def build_dry_run_payload(
    *,
    candidate: dict[str, Any],
    application: dict[str, Any],
    job_id: str,
    careers_base_url: str | None,
    apply_url: str | None,
    odata_base_url: str | None,
    company_id: str | None,
    locale: str,
    resume_file: ResumeFile | None = None,
    attachment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preview envelope for dry-run (no OData network)."""
    ready = bool(odata_base_url and company_id)
    payload: dict[str, Any] = {
        "successfactors_route": "odata_recruiting" if ready else "portal_blocked",
        "job_req_id": job_id,
        "careers_base_url": careers_base_url,
        "talentcommunity_apply_url": apply_url,
        "locale": locale,
        "odata_base_url": odata_base_url,
        "company_id": company_id,
        "candidate": candidate,
        "application": _redact_application(application),
        "blocker": None if ready else _LIVE_BLOCKER,
    }
    meta = resume_meta_for_payload(resume_file)
    if meta is not None:
        payload["resume"] = meta
    if attachment is not None:
        # Never echo Base64 resume bytes into application_log previews.
        payload["attachment"] = {
            key: ("<omitted>" if key == "fileContent" else value)
            for key, value in attachment.items()
        }
    return payload


def _redact_application(application: dict[str, Any]) -> dict[str, Any]:
    """Drop nested binary / oversized fields from dry-run application previews."""
    return {key: value for key, value in application.items() if key != "fileContent"}
