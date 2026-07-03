"""Tests for the Uber Careers apply adapter."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.uber_careers import UberCareersApplier
from app.appliers.adapters.uber_careers_common import (
    api_url,
    apply_form_url,
    resolve_job_id,
    resolve_session_token,
    yes_no_answer,
)
from app.appliers.adapters.uber_careers_payload import (
    build_application_form_request,
    build_phone_number,
    build_positions,
)
from app.appliers.adapters.uber_careers_questions import (
    build_question_responses,
    missing_required_answers,
    normalize_question,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData, ProfileLinks, ResumeFile
from tests.conftest import load_json_fixture, make_http_client

JOB_URL = "https://www.uber.com/us/en/careers/list/154672"
JOB_ID = "154672"


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="San Francisco, CA, US",
        links=ProfileLinks(
            linkedin="https://linkedin.com/in/ada",
            github="https://github.com/ada",
            website="https://ada.example",
        ),
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={
            "legal_right_to_work": "Yes",
            "in_usa": "Yes",
            "require_visa_sponsorship": "No",
            "screening_years_experience": "6+",
        },
        work_experience=[
            {
                "job_title": "Staff Engineer",
                "company": "Example Corp",
                "location": "San Francisco, CA",
                "start_month": 1,
                "start_year": 2020,
                "is_current": True,
            }
        ],
        education=[
            {
                "school": "Example University",
                "degree": "BS",
                "field_of_study": "Computer Science",
                "end_year": 2019,
            }
        ],
        skills=["Python", "Distributed systems"],
    )


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {},
        "headers": {},
        "session": {"session_token": "uber-session-token"},
    }


def _handlers() -> dict[str, object]:
    questions = load_json_fixture("uber_careers_additional_questions.json")
    submit_success = load_json_fixture("uber_careers_submit_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(api_url("getAdditionalQuestionsForJob")):
            return httpx.Response(200, json=questions)
        if url.endswith("/careers/apply/graphql"):
            return httpx.Response(200, json=submit_success)
        return httpx.Response(404, text="not found")

    return {"handler": handler, "questions": questions, "submit_success": submit_success}


def test_has_applier_registers_uber_careers() -> None:
    assert has_applier("uber_careers")


def test_resolve_job_id_and_session_token() -> None:
    assert resolve_job_id({}, JOB_URL, JOB_ID) == 154672
    assert resolve_job_id({"job_id": 99}, "", "ignored") == 99
    assert resolve_job_id({}, "https://example.com/jobs/1", "x") is None
    assert resolve_session_token(_credentials(), {}) == "uber-session-token"
    assert resolve_session_token(None, {"sessionToken": "cfg-token"}) == "cfg-token"


def test_yes_no_answer_normalizes_values() -> None:
    assert yes_no_answer({"legal_right_to_work": "yes"}, "legal_right_to_work") == "Yes"
    assert yes_no_answer({"legal_right_to_work": "false"}, "legal_right_to_work") == "No"


def test_normalize_question_and_responses() -> None:
    raw = load_json_fixture("uber_careers_additional_questions.json")["data"][
        "additionalQuestions"
    ][0]
    normalized = normalize_question(raw)
    assert normalized["question_id"] == "Q123"
    assert normalized["form_question_id"] == "screening_years_experience"

    responses = build_question_responses([raw], _profile().answers)
    assert responses == [{"questionID": "Q123", "answer": "6+"}]


def test_missing_required_answers_detects_gaps() -> None:
    raw = load_json_fixture("uber_careers_additional_questions.json")["data"]["additionalQuestions"]
    assert missing_required_answers(raw, {}) == ["How many years of experience do you have?"]
    assert not missing_required_answers(raw, _profile().answers)


def test_build_phone_number_parses_e164() -> None:
    phone = build_phone_number(_profile())
    assert phone == {"countryCode": "1", "number": "5550100"}


def test_build_application_form_request_maps_profile() -> None:
    raw_questions = load_json_fixture("uber_careers_additional_questions.json")["data"][
        "additionalQuestions"
    ]
    request = build_application_form_request(
        _profile(),
        job_id=154672,
        job_title="Staff Software Engineer",
        session_token="preview-token",
        additional_questions=raw_questions,
        resume_file=None,
        include_resume_bytes=False,
    )
    assert request["jobID"] == 154672
    assert request["emailAddress"] == "ada@example.com"
    assert request["legalRightToWork"] == "Yes"
    assert request["linkedInURL"] == "https://linkedin.com/in/ada"
    assert request["additionalQuestionsResponses"] == [{"questionID": "Q123", "answer": "6+"}]
    assert len(request["positions"]) == 1
    assert request["positions"][0]["companyName"] == "Example Corp"


def test_build_positions_requires_month_and_year() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            {
                "job_title": "Engineer",
                "company": "Example Corp",
                "start_year": 2020,
            }
        ],
    )
    assert build_positions(profile) == []


def test_uber_careers_dry_run() -> None:
    fixtures = _handlers()
    applier = UberCareersApplier(http=make_http_client(fixtures["handler"]))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Staff Software Engineer",
            company="Uber",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["job_id"] == 154672
    assert result.payload["application_form_request"]["sessionToken"] == ""


def test_uber_careers_live_submit() -> None:
    fixtures = _handlers()
    applier = UberCareersApplier(http=make_http_client(fixtures["handler"]))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Staff Software Engineer",
            company="Uber",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            resume_file=ResumeFile(
                filename="resume.pdf",
                content_type="application/pdf",
                size_bytes=4,
                data=b"%PDF",
            ),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "True"
    assert result.payload is not None
    assert result.payload["attachments_submitted"] is True


def test_uber_careers_live_submit_requires_session_token() -> None:
    fixtures = _handlers()
    applier = UberCareersApplier(http=make_http_client(fixtures["handler"]))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Staff Software Engineer",
            company="Uber",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "session_token" in (result.error or "")


def test_get_applier_returns_registered_instance() -> None:
    applier = get_applier("uber_careers", http=make_http_client(lambda _: httpx.Response(200)))
    assert isinstance(applier, UberCareersApplier)


def test_apply_form_url_matches_careers_locale_path() -> None:
    assert apply_form_url(154672) == "https://www.uber.com/us/en/careers/apply/form/154672"
    assert (
        apply_form_url(154672, locale_path="global/en")
        == "https://www.uber.com/global/en/careers/apply/form/154672"
    )
