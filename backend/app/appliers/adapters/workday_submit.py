"""Workday CXS live application submission."""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.workday_common import (
    WorkdayTarget,
    build_name_body,
    cxs_jobapplication_url,
    request_headers,
)
from app.appliers.adapters.workday_questionnaire import submit_terms_consent
from app.appliers.adapters.workday_resume import upload_resume_attachment
from app.appliers.adapters.workday_submit_payload import (
    LiveSubmitProgress,
    extract_error_message,
)
from app.appliers.adapters.workday_submit_sections import (
    submit_profile_sections,
    submit_questionnaire_sections,
)
from app.appliers.types import ApplyResult
from app.schemas.profile import ProfileData, ResumeFile
from app.scrapers.http import HttpClient


def submit_live_application(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    job_path: str,
    job_posting_id: str,
    profile_payload: dict[str, Any],
    profile: ProfileData,
    resume_file: ResumeFile | None,
    config: dict[str, Any],
    csrf_token: str,
    credentials: dict[str, dict[str, str]] | None,
) -> ApplyResult:
    """Create the application, submit sections, and finalize."""
    create_url = f"{target.api_base()}/jobpostings/{job_posting_id}/jobapplications"
    headers = request_headers(target, job_path, csrf_token=csrf_token, credentials=credentials)
    try:
        created = http.post_json(create_url, json={}, headers=headers)
    except httpx.HTTPError as exc:
        return ApplyResult(
            status="failed",
            error=str(exc),
            payload=profile_payload,
        )

    if not isinstance(created, dict):
        return ApplyResult(
            status="failed",
            error="workday apply returned an unexpected create response",
            payload=profile_payload,
        )

    application_id = created.get("id")
    session_id = created.get("sessionId")
    if not application_id:
        message = extract_error_message(created)
        return ApplyResult(
            status="failed",
            error=message or "workday did not create an application (sign in required?)",
            payload=profile_payload,
        )

    application_id_str = str(application_id)
    session_token = str(session_id or "")
    progress = LiveSubmitProgress(profile_payload=profile_payload)

    name_url = cxs_jobapplication_url(target, application_id_str, "name")
    name_headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    try:
        named = http.post_json(
            name_url,
            json=build_name_body(profile, config),
            headers=name_headers,
        )
    except httpx.HTTPError as exc:
        return ApplyResult(
            status="failed",
            error=str(exc),
            payload=profile_payload,
            external_application_id=application_id_str,
        )
    if isinstance(named, dict) and named.get("errorCode"):
        return ApplyResult(
            status="failed",
            error=extract_error_message(named) or "workday name rejected",
            payload=profile_payload,
            external_application_id=application_id_str,
        )

    if resume_file is not None and not config.get("skip_resume_upload"):
        try:
            progress.resume_result = upload_resume_attachment(
                http,
                target=target,
                application_id=application_id_str,
                resume_file=resume_file,
                job_path=job_path,
                csrf_token=csrf_token,
                session_id=session_token,
                credentials=credentials,
            )
        except ValueError as exc:
            return ApplyResult(
                status="failed",
                error=str(exc),
                payload=progress.as_payload(),
                external_application_id=application_id_str,
            )

    if failed := submit_profile_sections(
        http,
        target=target,
        application_id=application_id_str,
        profile=profile,
        job_path=job_path,
        config=config,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
        progress=progress,
    ):
        return failed

    if failed := submit_questionnaire_sections(
        http,
        target=target,
        application_id=application_id_str,
        profile=profile,
        job_path=job_path,
        config=config,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
        progress=progress,
    ):
        return failed

    if config.get("auto_terms_consent"):
        try:
            terms = submit_terms_consent(
                http,
                target=target,
                application_id=application_id_str,
                csrf_token=csrf_token,
                session_id=session_token,
                credentials=credentials,
            )
        except httpx.HTTPError as exc:
            return progress.failure(str(exc), application_id_str)
        if isinstance(terms, dict) and terms.get("errorCode"):
            return progress.failure(
                extract_error_message(terms) or "workday terms consent rejected",
                application_id_str,
            )

    finalize_url = cxs_jobapplication_url(target, application_id_str, "finalize")
    finalize_headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    try:
        finalized = http.post_json(finalize_url, json={}, headers=finalize_headers)
    except httpx.HTTPError as exc:
        return progress.failure(str(exc), application_id_str)

    if isinstance(finalized, dict) and finalized.get("errorCode"):
        return progress.failure(
            extract_error_message(finalized) or "workday finalize rejected",
            application_id_str,
        )

    return ApplyResult(
        status="submitted",
        payload=progress.as_payload(),
        external_application_id=application_id_str,
    )
