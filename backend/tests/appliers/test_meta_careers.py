"""Tests for the Meta Careers apply adapter."""

import json
from collections.abc import Callable

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.meta_careers import MetaCareersApplier
from app.appliers.adapters.meta_careers_common import (
    apply_url,
    extract_application_id,
    public_job_url,
    resolve_requisition_id,
)
from app.appliers.adapters.meta_careers_detail import parse_job_detail_response
from app.appliers.adapters.meta_careers_payload import (
    build_application_payload,
    build_application_state,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ApplyProfile, EducationEntry, ProfileData, ResumeFile
from tests.conftest import load_fixture, load_json_fixture, make_http_client

JOB_ID = "2132019417725760"
JOB_URL = f"https://www.metacareers.com/jobs/{JOB_ID}/"
DETAIL_FIXTURE = "meta_careers_job_details.json"
PAGE_FIXTURE = "meta_careers_page.html"
SUBMIT_FIXTURE = {
    "data": {
        "xcp_create_application_v2": {
            "application_id": "app-123",
            "consideration": {"id": "consideration-456", "job_title": "TPM"},
        }
    }
}


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Menlo Park, CA",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"work_authorization": "Yes"},
        work_experience=[
            {
                "job_title": "Software Engineer",
                "company": "Example Corp",
                "location": "San Francisco, CA",
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
        links={"linkedin": "https://www.linkedin.com/in/ada", "website": "", "github": ""},
    )


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"c_user": "123", "xs": "abc"},
        "headers": {},
        "session": {"session_id": "session-xyz", "lsd": "csrf-token"},
    }


def _graphql_handler(
    page_fixture: str,
    detail_fixture: str,
    *,
    on_submit: Callable[[httpx.Request, str], None] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=page_fixture)
        body = request.content.decode()
        if "CandidatePortalJobDetailsViewQuery" in body:
            return httpx.Response(
                200,
                text=detail_fixture,
                headers={"content-type": "application/json"},
            )
        if on_submit is not None:
            on_submit(request, body)
        return httpx.Response(
            200,
            text=json.dumps(SUBMIT_FIXTURE),
            headers={"content-type": "application/json"},
        )

    return handler


def test_has_applier_registers_meta_careers() -> None:
    assert has_applier("meta_careers")


def test_resolve_requisition_id_and_urls() -> None:
    assert resolve_requisition_id({}, JOB_URL, JOB_ID) == JOB_ID
    assert (
        resolve_requisition_id(
            {},
            f"https://www.metacareers.com/profile/job_details/{JOB_ID}/",
            JOB_ID,
        )
        == JOB_ID
    )
    assert resolve_requisition_id({"requisition_id": "999"}, "", "ignored") == "999"
    assert public_job_url(JOB_ID) == JOB_URL
    assert apply_url(JOB_ID).endswith(f"/profile/create_application/{JOB_ID}/")


def test_parse_job_detail_fixture() -> None:
    detail = parse_job_detail_response(load_json_fixture(DETAIL_FIXTURE), requisition_id=JOB_ID)
    assert detail.requisition_id == JOB_ID
    assert detail.title == "Technical Program Manager, MTIA Software"
    assert detail.locations == ("Menlo Park, CA",)
    assert len(detail.minimum_qualifications) >= 3


def test_build_application_state_maps_profile_fields() -> None:
    detail = parse_job_detail_response(load_json_fixture(DETAIL_FIXTURE), requisition_id=JOB_ID)
    state = build_application_state(
        detail,
        _profile(),
        company="Meta",
        job_title=detail.title,
    )
    assert state["candidateEmail"] == "ada@example.com"
    assert state["candidateFirstName"] == "Ada"
    assert state["workEmployerNames"] == ["Example Corp"]
    assert state["collegeSchoolNames"] == ["Example University"]
    assert state["collegeDegreeNames"] == ["BS"]
    assert state["collegeConcentration1Names"] == ["Computer Science"]
    assert state["workEligibleUS"] == "0"


def test_build_application_state_keeps_education_arrays_aligned() -> None:
    """School-only rows must not drop degree/field slots (APL-06)."""
    detail = parse_job_detail_response(load_json_fixture(DETAIL_FIXTURE), requisition_id=JOB_ID)
    profile = _profile()
    profile.education = [
        EducationEntry(school="Community College"),
        EducationEntry(
            school="Example University",
            degree="BS",
            field_of_study="Computer Science",
        ),
    ]
    state = build_application_state(
        detail,
        profile,
        company="Meta",
        job_title=detail.title,
    )
    assert state["collegeSchoolNames"] == ["Community College", "Example University"]
    assert state["collegeDegreeNames"] == ["", "BS"]
    assert state["collegeConcentration1Names"] == ["", "Computer Science"]


def test_dry_run_fetches_job_and_returns_payload() -> None:
    page_fixture = load_fixture(PAGE_FIXTURE)
    detail_fixture = load_fixture(DETAIL_FIXTURE)
    seen: dict[str, list[str]] = {"urls": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["urls"].append(str(request.url))
        response = _graphql_handler(page_fixture, detail_fixture)(request)
        if request.method == "POST":
            assert request.headers.get("x-fb-friendly-name") == "CandidatePortalJobDetailsViewQuery"
        return response

    applier = get_applier("meta_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Technical Program Manager, MTIA Software",
            company="Meta",
            job_url=JOB_URL,
            config={"company": "Meta"},
            profile=_profile(),
            dry_run=True,
        )
    )

    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["requisition_id"] == JOB_ID
    assert result.payload["application"]["candidateEmail"] == "ada@example.com"
    assert any("job_details" in url for url in seen["urls"])


def test_live_submit_posts_create_application_mutation() -> None:
    seen: dict[str, object] = {}

    def on_submit(request: httpx.Request, body: str) -> None:
        seen["submit_headers"] = dict(request.headers)
        seen["submit_body"] = body
        assert "CandidateChatbotApplicationDetailSubmitMutation" in body

    handler = _graphql_handler(
        load_fixture(PAGE_FIXTURE),
        load_fixture(DETAIL_FIXTURE),
        on_submit=on_submit,
    )
    applier = MetaCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Technical Program Manager, MTIA Software",
            company="Meta",
            job_url=JOB_URL,
            config={"company": "Meta"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert extract_application_id(SUBMIT_FIXTURE) == "app-123"
    assert result.external_application_id == "app-123"
    assert result.payload is not None
    assert result.payload["submit_input"]["session_id"] == "session-xyz"
    headers = seen["submit_headers"]
    assert headers.get("x-fb-lsd") == "csrf-token"


def test_live_submit_with_resume_uses_multipart() -> None:
    def on_submit(request: httpx.Request, body: str) -> None:
        content_type = request.headers.get("content-type", "")
        assert "multipart/form-data" in content_type
        assert "CandidateChatbotApplicationDetailSubmitMutation" in body

    handler = _graphql_handler(
        load_fixture(PAGE_FIXTURE),
        load_fixture(DETAIL_FIXTURE),
        on_submit=on_submit,
    )
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    applier = MetaCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Technical Program Manager, MTIA Software",
            company="Meta",
            job_url=JOB_URL,
            config={"company": "Meta"},
            profile=profile,
            resume_file=resume,
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.payload is not None
    assert result.payload["submit_input"]["candidateResumeFile"] == "candidateResumeFile"


def test_live_submit_with_resume_fails_on_graphql_errors() -> None:
    """Multipart resume submit must not report submitted on GraphQL errors (APL-05)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=load_fixture(PAGE_FIXTURE))
        body = request.content.decode()
        if "CandidatePortalJobDetailsViewQuery" in body:
            return httpx.Response(
                200,
                text=load_fixture(DETAIL_FIXTURE),
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            200,
            json={"errors": [{"message": "attachment rejected"}]},
            headers={"content-type": "application/json"},
        )

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    applier = MetaCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Technical Program Manager, MTIA Software",
            company="Meta",
            job_url=JOB_URL,
            config={"company": "Meta"},
            profile=profile,
            resume_file=resume,
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert "attachment rejected" in (result.error or "")


def test_live_submit_requires_session_cookies() -> None:
    handler = _graphql_handler(load_fixture(PAGE_FIXTURE), load_fixture(DETAIL_FIXTURE))
    applier = MetaCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Technical Program Manager, MTIA Software",
            company="Meta",
            job_url=JOB_URL,
            config={"company": "Meta"},
            profile=_profile(),
            credentials={
                "cookies": {},
                "headers": {},
                "session": {"session_id": "s1", "lsd": "l1"},
            },
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert "cookies" in result.error


def test_build_application_payload_includes_resume_metadata_on_dry_run() -> None:
    detail = parse_job_detail_response(load_json_fixture(DETAIL_FIXTURE), requisition_id=JOB_ID)
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    payload = build_application_payload(
        detail,
        _profile(),
        company="Meta",
        job_title=detail.title,
        resume_file=resume,
    )
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert payload["application"]["candidateResumeFileName"] == "resume.pdf"
