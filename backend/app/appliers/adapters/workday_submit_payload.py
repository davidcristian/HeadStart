"""Payload assembly for live Workday application submission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.appliers.adapters.workday_experience import SectionSubmitResult, sections_payload
from app.appliers.adapters.workday_questionnaire import QuestionnaireSubmitResult
from app.appliers.types import ApplyResult


@dataclass
class LiveSubmitProgress:
    """Accumulates section results while submitting a live Workday application."""

    profile_payload: dict[str, Any]
    resume_result: dict[str, Any] | None = None
    experience_results: list[SectionSubmitResult] | None = None
    education_results: list[SectionSubmitResult] | None = None
    skill_results: list[SectionSubmitResult] | None = None
    language_results: list[SectionSubmitResult] | None = None
    questionnaire_results: list[QuestionnaireSubmitResult] | None = None

    def as_payload(self) -> dict[str, Any]:
        """Merge accumulated section results into the profile payload."""
        return build_live_payload(
            self.profile_payload,
            resume_result=self.resume_result,
            experience_results=self.experience_results,
            education_results=self.education_results,
            skill_results=self.skill_results,
            language_results=self.language_results,
            questionnaire_results=self.questionnaire_results,
        )

    def failure(self, error: str, application_id: str) -> ApplyResult:
        """Build a failed ApplyResult with the progress collected so far."""
        return ApplyResult(
            status="failed",
            error=error,
            payload=self.as_payload(),
            external_application_id=application_id,
        )


def build_live_payload(
    profile_payload: dict[str, Any],
    *,
    resume_result: dict[str, Any] | None = None,
    experience_results: list[SectionSubmitResult] | None = None,
    education_results: list[SectionSubmitResult] | None = None,
    skill_results: list[SectionSubmitResult] | None = None,
    language_results: list[SectionSubmitResult] | None = None,
    questionnaire_results: list[QuestionnaireSubmitResult] | None = None,
) -> dict[str, Any]:
    """Attach submitted section snapshots to the base profile payload."""
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


def extract_error_message(response: dict[str, Any]) -> str | None:
    """Best-effort Workday CXS error message from a JSON body."""
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
