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
from app.appliers.adapters.workday_experience import (
    SectionSubmitResult,
    sections_payload,
    submit_educations,
    submit_work_experiences,
)
from app.appliers.adapters.workday_skills import submit_languages, submit_skills
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

    experience_results = submit_work_experiences(
        http,
        target=target,
        application_id=str(application_id),
        profile=profile,
        job_path=job_path,
        config=config,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    failed_experience = next((r for r in experience_results if not r.ok), None)
    if failed_experience is not None:
        return ApplyResult(
            status="failed",
            error=failed_experience.error or "workday work experience submit failed",
            payload=_live_payload(
                profile_payload,
                resume_result=resume_result,
                experience_results=experience_results,
            ),
            external_application_id=str(application_id),
        )

    education_results = submit_educations(
        http,
        target=target,
        application_id=str(application_id),
        profile=profile,
        job_path=job_path,
        config=config,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    failed_education = next((r for r in education_results if not r.ok), None)
    if failed_education is not None:
        return ApplyResult(
            status="failed",
            error=failed_education.error or "workday education submit failed",
            payload=_live_payload(
                profile_payload,
                resume_result=resume_result,
                experience_results=experience_results,
                education_results=education_results,
            ),
            external_application_id=str(application_id),
        )

    skill_results = submit_skills(
        http,
        target=target,
        application_id=str(application_id),
        profile=profile,
        job_path=job_path,
        config=config,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    failed_skill = next((r for r in skill_results if not r.ok), None)
    if failed_skill is not None:
        return ApplyResult(
            status="failed",
            error=failed_skill.error or "workday skills submit failed",
            payload=_live_payload(
                profile_payload,
                resume_result=resume_result,
                experience_results=experience_results,
                education_results=education_results,
                skill_results=skill_results,
            ),
            external_application_id=str(application_id),
        )

    language_results = submit_languages(
        http,
        target=target,
        application_id=str(application_id),
        profile=profile,
        job_path=job_path,
        config=config,
        csrf_token=csrf_token,
        session_id=session_token,
        credentials=credentials,
    )
    failed_language = next((r for r in language_results if not r.ok), None)
    if failed_language is not None:
        return ApplyResult(
            status="failed",
            error=failed_language.error or "workday languages submit failed",
            payload=_live_payload(
                profile_payload,
                resume_result=resume_result,
                experience_results=experience_results,
                education_results=education_results,
                skill_results=skill_results,
                language_results=language_results,
            ),
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
            payload=_live_payload(
                profile_payload,
                resume_result=resume_result,
                experience_results=experience_results,
                education_results=education_results,
                skill_results=skill_results,
                language_results=language_results,
                questionnaire_results=questionnaire_results,
            ),
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
                payload=_live_payload(
                    profile_payload,
                    resume_result=resume_result,
                    experience_results=experience_results,
                    education_results=education_results,
                    skill_results=skill_results,
                    language_results=language_results,
                    questionnaire_results=questionnaire_results,
                ),
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
            payload=_live_payload(
                profile_payload,
                resume_result=resume_result,
                experience_results=experience_results,
                education_results=education_results,
                skill_results=skill_results,
                language_results=language_results,
                questionnaire_results=questionnaire_results,
            ),
            external_application_id=str(application_id),
        )

    if isinstance(finalized, dict) and finalized.get("errorCode"):
        return ApplyResult(
            status="failed",
            error=_extract_error_message(finalized) or "workday finalize rejected",
            payload=_live_payload(
                profile_payload,
                resume_result=resume_result,
                experience_results=experience_results,
                education_results=education_results,
                skill_results=skill_results,
                language_results=language_results,
                questionnaire_results=questionnaire_results,
            ),
            external_application_id=str(application_id),
        )

    return ApplyResult(
        status="submitted",
        payload=_live_payload(
            profile_payload,
            resume_result=resume_result,
            experience_results=experience_results,
            education_results=education_results,
            skill_results=skill_results,
            language_results=language_results,
            questionnaire_results=questionnaire_results,
        ),
        external_application_id=str(application_id),
    )


def _live_payload(
    profile_payload: dict[str, Any],
    *,
    resume_result: dict[str, Any] | None = None,
    experience_results: list[SectionSubmitResult] | None = None,
    education_results: list[SectionSubmitResult] | None = None,
    skill_results: list[SectionSubmitResult] | None = None,
    language_results: list[SectionSubmitResult] | None = None,
    questionnaire_results: list[QuestionnaireSubmitResult] | None = None,
) -> dict[str, Any]:
    payload = dict(profile_payload)
    if resume_result:
        payload["resumeAttachments"] = resume_result
    if experience_results:
        payload["workExperiences"] = sections_payload(experience_results)
    if education_results:
        payload["educations"] = sections_payload(education_results)
    if skill_results:
        payload["skills"] = sections_payload(skill_results)
    if language_results:
        payload["languages"] = sections_payload(language_results)
    if questionnaire_results:
        payload["questionnaires"] = _questionnaire_payload(questionnaire_results)
    return payload


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
