"""Tests for the Uber Careers apply adapter (end-to-end apply flow)."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.uber_careers import UberCareersApplier
from app.appliers.adapters.uber_careers_common import (
    api_url,
    apply_form_url,
)
from app.appliers.base import get_applier
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
            credentials=_credentials(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["job_id"] == 154672
    # Live session token must not land in the persisted dry-run payload (APL-21).
    assert result.payload["application_form_request"]["sessionToken"] == ""
    assert "uber-session-token" not in str(result.payload)


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


def test_apply_fails_without_resolvable_job_id() -> None:
    applier = UberCareersApplier(http=make_http_client(lambda _: httpx.Response(200)))
    result = applier.apply(
        ApplyContext(
            job_external_id="not-a-number",
            job_title="Staff Software Engineer",
            company="Uber",
            job_url="https://example.com/jobs/nope",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "numeric job id" in (result.error or "")


def test_live_apply_fails_when_required_answers_missing() -> None:
    fixtures = _handlers()
    profile = _profile()
    profile.answers = {}
    applier = UberCareersApplier(http=make_http_client(fixtures["handler"]))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Staff Software Engineer",
            company="Uber",
            job_url=JOB_URL,
            config={},
            profile=profile,
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "missing required screening answers" in (result.error or "")


def test_apply_wraps_value_error_from_question_fetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "data": {"message": "boom"}})

    applier = UberCareersApplier(http=make_http_client(handler))
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
    assert result.status == "failed"
    assert "boom" in (result.error or "")


def test_apply_wraps_http_error_from_question_fetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    applier = UberCareersApplier(http=make_http_client(handler))
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
    assert result.status == "failed"
    assert result.error


def test_live_submit_wraps_value_error_from_graphql() -> None:
    questions = load_json_fixture("uber_careers_additional_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(api_url("getAdditionalQuestionsForJob")):
            return httpx.Response(200, json=questions)
        if url.endswith("/careers/apply/graphql"):
            return httpx.Response(200, json={"errors": [{"message": "denied"}]})
        return httpx.Response(404, text="not found")

    applier = UberCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Staff Software Engineer",
            company="Uber",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "denied" in (result.error or "")


def test_live_submit_wraps_http_error_from_graphql() -> None:
    questions = load_json_fixture("uber_careers_additional_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(api_url("getAdditionalQuestionsForJob")):
            return httpx.Response(200, json=questions)
        if url.endswith("/careers/apply/graphql"):
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(404, text="not found")

    applier = UberCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Staff Software Engineer",
            company="Uber",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error
