"""Tests for Workday live-submit payload assembly."""

from app.appliers.adapters.workday_experience import SectionSubmitResult
from app.appliers.adapters.workday_questionnaire import QuestionnaireSubmitResult
from app.appliers.adapters.workday_submit_payload import (
    LiveSubmitProgress,
    build_live_payload,
    extract_error_message,
    mid_flow_failure,
)


def test_extract_error_message_prefers_message() -> None:
    assert extract_error_message({"message": "  Sign in required  "}) == "Sign in required"


def test_extract_error_message_falls_back_to_error_code() -> None:
    assert extract_error_message({"message": "   ", "errorCode": "AUTH"}) == "AUTH"
    assert extract_error_message({"errorCode": 42}) == "42"


def test_extract_error_message_returns_none_without_error() -> None:
    assert extract_error_message({"message": 123}) is None
    assert extract_error_message({}) is None


def test_build_live_payload_attaches_all_sections() -> None:
    experience = [SectionSubmitResult(section="workexperiences", index=0, payload={"a": 1})]
    education = [SectionSubmitResult(section="educations", index=0, payload={"b": 2})]
    skills = [SectionSubmitResult(section="skills", index=0, payload={"c": 3})]
    languages = [SectionSubmitResult(section="languages", index=0, payload={"d": 4})]
    questionnaires = [
        QuestionnaireSubmitResult(
            qtype="primary",
            questionnaire_id="q-1",
            answers=[{"x": 1}],
            response={"id": "resp-1"},
        )
    ]
    payload = build_live_payload(
        {"jobPostingId": "job-1"},
        resume_result={"upload": {}},
        experience_results=experience,
        education_results=education,
        skill_results=skills,
        language_results=languages,
        questionnaire_results=questionnaires,
    )
    assert payload["resumeAttachments"] == {"upload": {}}
    assert "workExperiences" in payload
    assert "educations" in payload
    assert "skills" in payload
    assert "languages" in payload
    assert payload["questionnaires"]["primary"]["responseId"] == "resp-1"


def test_build_live_payload_omits_empty_sections() -> None:
    payload = build_live_payload({"jobPostingId": "job-1"})
    assert payload == {"jobPostingId": "job-1"}


def test_questionnaire_payload_includes_error_without_response() -> None:
    questionnaires = [
        QuestionnaireSubmitResult(
            qtype="secondary",
            questionnaire_id="q-2",
            answers=[],
            error="missing answers",
        )
    ]
    payload = build_live_payload({}, questionnaire_results=questionnaires)
    assert payload["questionnaires"]["secondary"]["error"] == "missing answers"
    assert "responseId" not in payload["questionnaires"]["secondary"]


def test_progress_failure_builds_failed_result() -> None:
    progress = LiveSubmitProgress(profile_payload={"jobPostingId": "job-1"})
    result = progress.failure("boom", "app-1")
    assert result.status == "failed"
    assert result.error is not None
    assert result.error.startswith("boom")
    assert "app-1" in result.error
    assert "partial Workday application" in result.error
    assert result.external_application_id == "app-1"
    assert result.payload == {"jobPostingId": "job-1", "partial_application": True}


def test_mid_flow_failure_flags_partial_application() -> None:
    result = mid_flow_failure("name rejected", "app-xyz", payload={"step": "name"})
    assert result.status == "failed"
    assert result.external_application_id == "app-xyz"
    assert result.payload == {"step": "name", "partial_application": True}
    assert result.error is not None
    assert "name rejected" in result.error
    assert "app-xyz" in result.error
