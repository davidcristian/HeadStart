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
from app.appliers.adapters.workday_questionnaire import (
    QuestionnaireSubmitResult,
    submit_questionnaires,
    submit_terms_consent,
)
from app.appliers.adapters.workday_resume import upload_resume_attachment
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
        message = _extract_error_message(created)
        return ApplyResult(
            status="failed",
            error=message or "workday did not create an application (sign in required?)",
            payload=profile_payload,
        )

    session_token = str(session_id or "")
    name_url = cxs_jobapplication_url(target, str(application_id), "name")
    name_headers = request_headers(
        target,
        job_path,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    try:
        http.post_json(
            name_url,
            json=build_name_body(profile, config),
            headers=name_headers,
        )
    except httpx.HTTPError as exc:
        return ApplyResult(
            status="failed",
            error=str(exc),
            payload=profile_payload,
            external_application_id=str(application_id),
        )

    resume_result: dict[str, Any] | None = None
    if resume_file is not None and not config.get("skip_resume_upload"):
        try:
            resume_result = upload_resume_attachment(
                http,
                target=target,
                application_id=str(application_id),
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
                payload={
                    **profile_payload,
                    "resumeAttachments": resume_result,
                },
                external_application_id=str(application_id),
            )

    questionnaire_results = submit_questionnaires(
        http,
        target=target,
        application_id=str(application_id),
        config=config,
        profile=profile,
        job_path=job_path,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    failed_questionnaire = next((r for r in questionnaire_results if not r.ok), None)
    if failed_questionnaire is not None:
        return ApplyResult(
            status="failed",
            error=failed_questionnaire.error or "workday questionnaire submit failed",
            payload={
                **profile_payload,
                **({"resumeAttachments": resume_result} if resume_result else {}),
                "questionnaires": _questionnaire_payload(questionnaire_results),
            },
            external_application_id=str(application_id),
        )

    if config.get("auto_terms_consent"):
        try:
            submit_terms_consent(
                http,
                target=target,
                application_id=str(application_id),
                csrf_token=csrf_token,
                session_id=session_token,
                credentials=credentials,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(
                status="failed",
                error=str(exc),
                payload={
                    **profile_payload,
                    **({"resumeAttachments": resume_result} if resume_result else {}),
                    "questionnaires": _questionnaire_payload(questionnaire_results),
                },
                external_application_id=str(application_id),
            )

    finalize_url = cxs_jobapplication_url(target, str(application_id), "finalize")
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
        return ApplyResult(
            status="failed",
            error=str(exc),
            payload={
                **profile_payload,
                **({"resumeAttachments": resume_result} if resume_result else {}),
                "questionnaires": _questionnaire_payload(questionnaire_results),
            },
            external_application_id=str(application_id),
        )

    if isinstance(finalized, dict) and finalized.get("errorCode"):
        return ApplyResult(
            status="failed",
            error=_extract_error_message(finalized) or "workday finalize rejected",
            payload={
                **profile_payload,
                **({"resumeAttachments": resume_result} if resume_result else {}),
                "questionnaires": _questionnaire_payload(questionnaire_results),
            },
            external_application_id=str(application_id),
        )

    return ApplyResult(
        status="submitted",
        payload={
            **profile_payload,
            **({"resumeAttachments": resume_result} if resume_result else {}),
            "questionnaires": _questionnaire_payload(questionnaire_results),
        },
        external_application_id=str(application_id),
    )


def _extract_error_message(response: dict[str, Any]) -> str | None:
    message = response.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    error_code = response.get("errorCode")
    if error_code:
        return str(error_code)
    return None


def _questionnaire_payload(results: list[QuestionnaireSubmitResult]) -> dict[str, Any]:
    return {
        result.qtype: {
            "questionnaireId": result.questionnaire_id,
            "questionnaireAnswers": result.answers,
            **({"error": result.error} if result.error else {}),
            **({"responseId": result.response.get("id")} if result.response else {}),
        }
        for result in results
    }
