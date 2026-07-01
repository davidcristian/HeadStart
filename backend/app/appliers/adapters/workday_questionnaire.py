"""Workday CXS questionnaire helpers for the apply adapter."""

from __future__ import annotations

from typing import Any, Literal

import httpx

from app.appliers.adapters.workday_common import (
    WorkdayTarget,
    calypso_common_url,
    calypso_jobapplication_url,
    cxs_jobapplication_url,
    fetch_job_posting_info,
    request_headers,
)
from app.appliers.adapters.workday_questionnaire_answers import build_questionnaire_answers
from app.schemas.profile import ProfileData
from app.scrapers.http import HttpClient

QuestionnaireType = Literal["primary", "secondary", "supplementary"]

_QUESTIONNAIRE_TYPES: tuple[QuestionnaireType, ...] = (
    "primary",
    "secondary",
    "supplementary",
)
_CONFIG_ID_KEYS: dict[QuestionnaireType, str] = {
    "primary": "questionnaire_id",
    "secondary": "secondary_questionnaire_id",
    "supplementary": "supplementary_questionnaire_id",
}
_POSTING_ID_KEYS: dict[QuestionnaireType, str] = {
    "primary": "questionnaireId",
    "secondary": "secondaryQuestionnaireId",
    "supplementary": "supplementaryQuestionnaireId",
}


class QuestionnaireSubmitResult:
    """Outcome of submitting one questionnaire type."""

    def __init__(
        self,
        *,
        qtype: QuestionnaireType,
        questionnaire_id: str,
        answers: list[dict[str, Any]],
        response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.qtype = qtype
        self.questionnaire_id = questionnaire_id
        self.answers = answers
        self.response = response
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None


def resolve_questionnaire_ids(
    config: dict[str, Any], job_posting_info: dict[str, Any] | None
) -> dict[QuestionnaireType, str | None]:
    """Questionnaire WIDs from config overrides or scraped job posting metadata."""
    posting = job_posting_info or {}
    resolved: dict[QuestionnaireType, str | None] = {}
    for qtype in _QUESTIONNAIRE_TYPES:
        configured = config.get(_CONFIG_ID_KEYS[qtype])
        if configured:
            resolved[qtype] = str(configured)
            continue
        posting_value = posting.get(_POSTING_ID_KEYS[qtype])
        resolved[qtype] = str(posting_value) if posting_value else None
    return resolved


def load_questionnaire(
    http: HttpClient,
    target: WorkdayTarget,
    questionnaire_id: str,
    *,
    credentials: dict[str, dict[str, str]] | None,
    csrf_token: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Fetch questionnaire definition from the public CXS API."""
    url = calypso_common_url(target, f"questionnaire/{questionnaire_id}")
    headers = request_headers(
        target,
        job_path="",
        csrf_token=csrf_token,
        session_id=session_id,
        form_definition=True,
        credentials=credentials,
    )
    data = http.get_json(url, headers=headers)
    if not isinstance(data, dict):
        raise ValueError("workday questionnaire response was not a JSON object")
    return data


def preview_questionnaires(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    config: dict[str, Any],
    profile: ProfileData,
    job_path: str,
    credentials: dict[str, dict[str, str]] | None,
    csrf_token: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Build questionnaire preview payloads without submitting."""
    if config.get("skip_questionnaires"):
        return {"jobPostingInfo": {}, "questionnaires": {}}

    posting_info = fetch_job_posting_info(http, target, job_path)
    questionnaire_ids = resolve_questionnaire_ids(config, posting_info)
    previews: dict[str, Any] = {}
    for qtype, questionnaire_id in questionnaire_ids.items():
        if not questionnaire_id or config.get(f"skip_{qtype}_questionnaire"):
            continue
        questionnaire = load_questionnaire(
            http,
            target,
            questionnaire_id,
            credentials=credentials,
            csrf_token=csrf_token,
            session_id=session_id,
        )
        answers, missing_required = build_questionnaire_answers(questionnaire, profile, config)
        previews[qtype] = {
            "questionnaireId": questionnaire_id,
            "questionnaireAnswers": answers,
            "missingRequiredQuestionIds": missing_required,
        }
    return {
        "jobPostingInfo": posting_info,
        "questionnaires": previews,
    }


def submit_questionnaires(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    config: dict[str, Any],
    profile: ProfileData,
    job_path: str,
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> list[QuestionnaireSubmitResult]:
    """Submit configured questionnaire types before finalize."""
    if config.get("skip_questionnaires"):
        return []

    posting_info = fetch_job_posting_info(http, target, job_path)
    questionnaire_ids = resolve_questionnaire_ids(config, posting_info)
    results: list[QuestionnaireSubmitResult] = []

    for qtype, questionnaire_id in questionnaire_ids.items():
        if not questionnaire_id or config.get(f"skip_{qtype}_questionnaire"):
            continue
        try:
            questionnaire = load_questionnaire(
                http,
                target,
                questionnaire_id,
                credentials=credentials,
                csrf_token=csrf_token,
                session_id=session_id,
            )
            answers, missing_required = build_questionnaire_answers(questionnaire, profile, config)
            if missing_required:
                results.append(
                    QuestionnaireSubmitResult(
                        qtype=qtype,
                        questionnaire_id=questionnaire_id,
                        answers=answers,
                        error=(
                            "missing required questionnaire answers for question ids: "
                            + ", ".join(missing_required)
                        ),
                    )
                )
                continue
            if not answers:
                continue
            response = _post_questionnaire_response(
                http,
                target=target,
                application_id=application_id,
                qtype=qtype,
                answers=answers,
                csrf_token=csrf_token,
                session_id=session_id,
                credentials=credentials,
            )
            results.append(
                QuestionnaireSubmitResult(
                    qtype=qtype,
                    questionnaire_id=questionnaire_id,
                    answers=answers,
                    response=response,
                )
            )
        except httpx.HTTPError as exc:
            results.append(
                QuestionnaireSubmitResult(
                    qtype=qtype,
                    questionnaire_id=questionnaire_id,
                    answers=[],
                    error=str(exc),
                )
            )
    return results


def submit_terms_consent(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> dict[str, Any]:
    """Accept terms and conditions when auto_terms_consent is enabled."""
    url = cxs_jobapplication_url(target, application_id, "termsandconditions")
    headers = request_headers(
        target,
        job_path="",
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    body = {"id": application_id, "acceptTermsAndAgreements": True}
    return http.put_json(url, json=body, headers=headers)


def _post_questionnaire_response(
    http: HttpClient,
    *,
    target: WorkdayTarget,
    application_id: str,
    qtype: QuestionnaireType,
    answers: list[dict[str, Any]],
    csrf_token: str,
    session_id: str,
    credentials: dict[str, dict[str, str]] | None,
) -> dict[str, Any]:
    suffix = f"jobapplication/{application_id}/questionnaireresponse?type={qtype}"
    url = calypso_jobapplication_url(target, suffix)
    headers = request_headers(
        target,
        job_path="",
        csrf_token=csrf_token,
        session_id=session_id,
        credentials=credentials,
    )
    response = http.post_json(
        url,
        json={"questionnaireAnswers": answers},
        headers=headers,
    )
    if not isinstance(response, dict):
        raise ValueError("workday questionnaireresponse returned an unexpected payload")
    if response.get("errorCode"):
        message = response.get("message") or response.get("errorCode")
        raise ValueError(str(message))
    return response
