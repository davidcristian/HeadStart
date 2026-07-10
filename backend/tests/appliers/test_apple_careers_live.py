"""Tests for the Apple Careers live-submit HTTP helpers."""

import httpx
import pytest

from app.appliers.adapters.apple_careers_detail import AppleCareersJobDetail
from app.appliers.adapters.apple_careers_live import (
    fetch_questionnaire,
    questionnaire_answers,
    upload_resume,
)
from app.appliers.types import ApplyContext
from app.schemas.profile import ProfileData, ResumeFile
from tests.conftest import make_http_client

_JSON_HEADERS = {"content-type": "application/json"}


def _detail() -> AppleCareersJobDetail:
    return AppleCareersJobDetail(
        position_id="REQ-1",
        job_number="1001",
        title="Engineer",
        job_type="REQ",
        pipeline_type="SWE",
        role_location_selection=False,
        managed_pipeline_role=False,
        transformed_posting_title="engineer",
        locale="en-us",
        locations=(),
    )


def _ctx() -> ApplyContext:
    return ApplyContext(
        job_external_id="REQ-1",
        job_title="Engineer",
        company="Apple",
        job_url="https://jobs.apple.com/en-us/details/REQ-1/engineer",
        profile=ProfileData(full_name="Ada Lovelace", email="a@b.com"),
    )


def test_fetch_questionnaire_returns_none_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    http = make_http_client(handler)
    assert fetch_questionnaire(http, _detail(), "csrf", _ctx()) is None


def test_fetch_questionnaire_returns_none_when_data_not_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "data": []}, headers=_JSON_HEADERS)

    http = make_http_client(handler)
    assert fetch_questionnaire(http, _detail(), "csrf", _ctx()) is None


def test_questionnaire_answers_guard_clauses() -> None:
    assert questionnaire_answers(None, {"a": "b"}) is None
    assert questionnaire_answers({"id": "q"}, {}) is None
    assert questionnaire_answers({"noId": "x"}, {"a": "b"}) is None
    assert questionnaire_answers({"id": "q"}, {"a": ""}) is None
    # No question ids in the questionnaire -> never dump profile.answers verbatim.
    assert questionnaire_answers({"id": "q"}, {"a": "b"}) is None


def test_questionnaire_answers_builds_payload() -> None:
    questionnaire = {
        "questionnaireId": "q9",
        "questions": [
            {"id": "work_auth"},
            {"questionId": "eeo_gender"},
            "not-a-dict",
            {"id": ""},
        ],
    }
    result = questionnaire_answers(
        questionnaire,
        {
            "work_auth": "Yes",
            "eeo_gender": "Decline",
            "skip": "",
            "unrelated_eeo": "leak me",
        },
    )
    assert result == {
        "id": "q9",
        "questionnaireId": "q9",
        "questionCategory": "APPLICATION",
        "answers": {"work_auth": "Yes", "eeo_gender": "Decline"},
        "reset": False,
    }


def test_questionnaire_answers_walks_sections_and_follow_ups() -> None:
    questionnaire = {
        "id": "q-root",
        "sections": [
            {
                "questions": [
                    {
                        "questionId": "parent",
                        "followUpQuestions": [{"id": "child"}],
                    }
                ]
            }
        ],
    }
    result = questionnaire_answers(
        questionnaire,
        {"parent": "A", "child": "B", "noise": "nope"},
    )
    assert result is not None
    assert result["answers"] == {"parent": "A", "child": "B"}


def test_questionnaire_answers_covers_walk_edge_cases() -> None:
    """Exercise duplicate ids, list containers, and non-dict section entries."""
    questionnaire = {
        "id": "q-edge",
        "fields": [
            # list-of-sections path (walk_container list branch)
            [
                {
                    "questions": [
                        {"id": "dup"},
                        {"questionId": "dup"},  # same id again -> seen skip
                        {"id": "empty_answer"},
                        {"id": "kept"},
                    ]
                },
                "not-a-section",  # non-dict container entry
            ]
        ],
        "questionSections": [{"questions": [{"id": "from_question_sections"}]}],
    }
    result = questionnaire_answers(
        questionnaire,
        {
            "dup": "once",
            "empty_answer": "",
            "kept": "yes",
            "from_question_sections": "qs",
        },
    )
    assert result is not None
    assert result["answers"] == {
        "dup": "once",
        "kept": "yes",
        "from_question_sections": "qs",
    }


def test_upload_resume_raises_without_file_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "data": {}}, headers=_JSON_HEADERS)

    http = make_http_client(handler)
    resume = ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    with pytest.raises(ValueError, match="did not return a file id"):
        upload_resume(http, "t1", resume, csrf_token="csrf", ctx=_ctx(), detail=_detail())
