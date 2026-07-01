"""Tests for Workday questionnaire helpers."""

import json

import httpx

from app.appliers.adapters.workday_common import WorkdayTarget, resolve_target
from app.appliers.adapters.workday_questionnaire import (
    build_questionnaire_answers,
    flatten_questions,
    preview_questionnaires,
    resolve_questionnaire_ids,
    submit_questionnaires,
)
from app.schemas.profile import ProfileData
from tests.conftest import load_json_fixture, make_http_client


def _target() -> WorkdayTarget:
    resolved = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert resolved is not None
    return resolved


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={
            "q-work-auth": "Yes",
            "q-notice": "2 weeks",
        },
    )


def test_resolve_questionnaire_ids_from_posting_info() -> None:
    posting = load_json_fixture("workday_job_posting_info.json")["jobPostingInfo"]
    ids = resolve_questionnaire_ids({}, posting)
    assert ids["primary"] == "quest-primary-001"
    assert ids["secondary"] == "quest-secondary-001"
    assert ids["supplementary"] is None


def test_flatten_questions_includes_branching_followups() -> None:
    questionnaire = {
        "questions": [
            {
                "id": "parent",
                "possibleAnswers": [
                    {
                        "id": "yes",
                        "branchingQuestion": {
                            "id": "child",
                            "possibleAnswers": [],
                        },
                    }
                ],
            }
        ]
    }
    flattened = flatten_questions(questionnaire)
    assert set(flattened) == {"parent", "child"}


def test_build_questionnaire_answers_maps_text_and_single_select() -> None:
    questionnaire = load_json_fixture("workday_questionnaire.json")
    answers, missing = build_questionnaire_answers(questionnaire, _profile(), {})
    assert missing == []
    assert len(answers) == 2
    assert answers[0]["questionItem"]["id"] == "q-work-auth"
    assert answers[0]["questionMultipleChoiceAnswers"] == ["ans-yes"]
    assert answers[1]["answerText"] == "2 weeks"


def test_build_questionnaire_answers_reports_missing_required() -> None:
    questionnaire = load_json_fixture("workday_questionnaire.json")
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={"q-notice": "2 weeks"},
    )
    answers, missing = build_questionnaire_answers(questionnaire, profile, {})
    assert answers == [{"questionItem": {"id": "q-notice"}, "answerText": "2 weeks"}]
    assert missing == ["q-work-auth"]


def test_preview_questionnaires_includes_answers_in_payload() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    preview = preview_questionnaires(
        make_http_client(handler),
        target=_target(),
        config={"skip_secondary_questionnaire": True},
        profile=_profile(),
        job_path="US-CA-Santa-Clara/Senior-Software-Engineer_JR1001",
        credentials=None,
        csrf_token=None,
        session_id=None,
    )
    assert preview["questionnaires"]["primary"]["questionnaireId"] == "quest-primary-001"
    primary_answers = preview["questionnaires"]["primary"]["questionnaireAnswers"]
    assert primary_answers[0]["questionMultipleChoiceAnswers"] == ["ans-yes"]


def test_submit_questionnaires_posts_each_type() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")
    response_fixture = load_json_fixture("workday_questionnaire_response.json")
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        if "questionnaireresponse" in request.url.path:
            body = json.loads(request.read().decode())
            assert body["questionnaireAnswers"][0]["questionMultipleChoiceAnswers"] == ["ans-yes"]
            return httpx.Response(200, json=response_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    results = submit_questionnaires(
        make_http_client(handler),
        target=_target(),
        application_id="app-abc123",
        config={"skip_secondary_questionnaire": True},
        profile=_profile(),
        job_path="US-CA-Santa-Clara/Senior-Software-Engineer_JR1001",
        csrf_token="csrf-token",
        session_id="sess-xyz789",
        credentials={
            "cookies": {"CALYPSO_SESSION": "session-token"},
            "headers": {},
            "session": {},
        },
    )
    assert len(results) == 1
    assert results[0].ok
    assert any("questionnaireresponse?type=primary" in url for url in seen_urls)
