"""Tests for the Microsoft Careers apply adapter."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.microsoft_careers import MicrosoftCareersApplier
from app.appliers.adapters.microsoft_careers_common import (
    extract_application_id,
    resolve_domain,
    resolve_position_id,
)
from app.appliers.adapters.microsoft_careers_payload import (
    build_answers,
    build_application_payload,
    build_candidate,
    build_submit_body,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client

JOB_ID = "1970393556869024"
JOB_URL = f"https://apply.careers.microsoft.com/careers/job/{JOB_ID}"
_JSON_HEADERS = {"content-type": "application/json"}


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Redmond, WA, US",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"work_authorization": "Yes"},
    )


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"_vs": "anon", "_vscid": "session-abc"},
        "headers": {},
        "session": {"csrf_token": "test-csrf-token-abc"},
    }


def test_has_applier_registers_microsoft_careers() -> None:
    assert has_applier("microsoft_careers")


def test_resolve_domain_and_position_id() -> None:
    assert resolve_domain({}) == "microsoft.com"
    assert resolve_domain({"domain": "contoso.com"}) == "contoso.com"
    assert resolve_position_id({}, JOB_URL, JOB_ID) == JOB_ID
    assert resolve_position_id({"position_id": "123"}, "", "fallback") == "123"


def test_build_candidate_maps_profile_fields() -> None:
    candidate = build_candidate(_profile(), job_title="Software Engineer", company="Microsoft")
    assert candidate["firstname"] == "Ada"
    assert candidate["lastname"] == "Lovelace"
    assert candidate["email"] == "ada@example.com"
    assert candidate["location"] == "Redmond, WA, US"
    assert candidate["location_detail"]["city"] == "Redmond"
    assert "Microsoft" in candidate["summary"]


def test_build_answers_uses_profile_answers() -> None:
    questions = json.loads(load_fixture("microsoft_careers_questions.json"))
    answers = build_answers(_profile(), questions)
    assert answers["work_authorization"] == "Yes"


def test_build_answers_is_driven_by_the_questionnaire() -> None:
    """Only answers the questionnaire actually asks for are submitted."""
    questions = json.loads(load_fixture("microsoft_careers_questions.json"))
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={
            "work_authorization": "Yes",  # matches a questionId
            "relocation": "",  # in the questionnaire but blank -> skipped
            "unlisted_note": "leak me",  # no matching questionId -> excluded
        },
    )
    answers = build_answers(profile, questions)
    assert answers == {"work_authorization": "Yes"}


def test_build_submit_body_shape() -> None:
    candidate = build_candidate(_profile(), job_title="Software Engineer", company="Microsoft")
    body = build_submit_body(
        domain="microsoft.com",
        position_id=JOB_ID,
        candidate=candidate,
        answers={"work_authorization": "Yes"},
    )
    assert body["pids"] == JOB_ID
    assert body["candidate"]["email"] == "ada@example.com"


def test_extract_application_id() -> None:
    assert extract_application_id({"data": {"application_id": "app-1"}}) == "app-1"
    assert extract_application_id({"id": 42}) == "42"


def test_dry_run_fetches_job_and_returns_payload() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")
    seen: dict[str, list[str]] = {"urls": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["urls"].append(str(request.url))
        if "/api/apply/v2/jobs/" in str(request.url):
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in str(request.url):
            return httpx.Response(
                200, text=questions_fixture, headers={"content-type": "application/json"}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("microsoft_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Engineer",
            company="Microsoft",
            job_url=JOB_URL,
            config={"domain": "microsoft.com"},
            profile=_profile(),
            dry_run=True,
        )
    )

    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["job"]["name"] == "Software Engineer/Sr Software Engineer"
    assert result.payload["candidate"]["email"] == "ada@example.com"
    assert result.payload["submit"]["pids"] == JOB_ID
    assert any("/api/apply/v2/jobs/" in url for url in seen["urls"])


def test_live_submit_posts_candidate_resume_and_submit() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")
    success_fixture = load_fixture("microsoft_careers_apply_success.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.setdefault("paths", []).append(request.url.path)
        if "/api/apply/v2/jobs/" in request.url.path:
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in request.url.path:
            return httpx.Response(
                200, text=questions_fixture, headers={"content-type": "application/json"}
            )
        if request.url.path.endswith("/api/apply/v2/candidate"):
            seen["candidate_body"] = json.loads(request.content.decode())
            return httpx.Response(200, json={"enc_id": 123})
        if request.url.path.endswith("/api/pcsx/upload_resume"):
            seen["resume_body"] = json.loads(request.content.decode())
            return httpx.Response(200, json={"status": 200, "data": {"candidate": {}}})
        if request.url.path.endswith("/api/application/v2/submit"):
            seen["submit_body"] = json.loads(request.content.decode())
            return httpx.Response(200, text=success_fixture, headers=_JSON_HEADERS)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Engineer",
            company="Microsoft",
            job_url=JOB_URL,
            config={"domain": "microsoft.com"},
            profile=profile,
            resume_file=resume,
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "app-998877"
    assert seen["candidate_body"]["email"] == "ada@example.com"
    assert seen["resume_body"]["resume_file_name"] == "resume.pdf"
    assert seen["submit_body"]["pids"] == JOB_ID


def test_live_submit_requires_session_cookies() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/apply/v2/jobs/" in str(request.url):
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in str(request.url):
            return httpx.Response(
                200, text=questions_fixture, headers={"content-type": "application/json"}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Engineer",
            company="Microsoft",
            job_url=JOB_URL,
            config={"domain": "microsoft.com"},
            profile=_profile(),
            credentials={"cookies": {}, "headers": {}, "session": {"csrf_token": "abc"}},
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert "session cookies" in result.error


def test_live_submit_fails_on_error_body() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/apply/v2/jobs/" in request.url.path:
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in request.url.path:
            return httpx.Response(
                200, text=questions_fixture, headers={"content-type": "application/json"}
            )
        if request.url.path.endswith("/api/apply/v2/candidate"):
            return httpx.Response(200, json={"enc_id": 123})
        if request.url.path.endswith("/api/application/v2/submit"):
            return httpx.Response(
                200,
                json={"success": False, "errors": [{"message": "duplicate application"}]},
                headers=_JSON_HEADERS,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Engineer",
            company="Microsoft",
            job_url=JOB_URL,
            config={"domain": "microsoft.com"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error == "duplicate application"


def test_live_submit_fails_when_candidate_post_errors() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/apply/v2/jobs/" in request.url.path:
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in request.url.path:
            return httpx.Response(
                200, text=questions_fixture, headers={"content-type": "application/json"}
            )
        if request.url.path.endswith("/api/apply/v2/candidate"):
            return httpx.Response(
                200,
                json={"success": False, "errors": [{"message": "invalid email"}]},
                headers=_JSON_HEADERS,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Engineer",
            company="Microsoft",
            job_url=JOB_URL,
            config={"domain": "microsoft.com"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error == "invalid email"


def test_live_submit_fails_when_resume_upload_errors() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/apply/v2/jobs/" in request.url.path:
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in request.url.path:
            return httpx.Response(
                200, text=questions_fixture, headers={"content-type": "application/json"}
            )
        if request.url.path.endswith("/api/apply/v2/candidate"):
            return httpx.Response(200, json={"enc_id": 123})
        if request.url.path.endswith("/api/pcsx/upload_resume"):
            return httpx.Response(
                200,
                json={"errors": [{"message": "resume too large"}]},
                headers=_JSON_HEADERS,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Engineer",
            company="Microsoft",
            job_url=JOB_URL,
            config={"domain": "microsoft.com"},
            profile=profile,
            resume_file=resume,
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error == "resume too large"


def test_build_application_payload_includes_resume_metadata_on_dry_run() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    candidate = build_candidate(_profile(), job_title="Software Engineer", company="Microsoft")
    payload = build_application_payload(
        domain="microsoft.com",
        position_id=JOB_ID,
        job_detail={"id": int(JOB_ID), "name": "Software Engineer"},
        questions={"default": {"fields": []}},
        candidate=candidate,
        answers={},
        resume_file=resume,
        include_resume_bytes=False,
    )
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert "resume_upload" not in payload


def test_apply_without_position_id_fails() -> None:
    applier = get_applier("microsoft_careers", http=make_http_client(_unexpected))
    result = applier.apply(
        ApplyContext(
            job_external_id="",
            job_title="Role",
            company="Microsoft",
            job_url="https://apply.careers.microsoft.com/careers/browse",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "position id" in (result.error or "")


def test_apply_fails_when_candidate_build_raises() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/apply/v2/jobs/" in str(request.url):
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in str(request.url):
            return httpx.Response(200, text=questions_fixture, headers=_JSON_HEADERS)
        raise AssertionError("unexpected")

    applier = get_applier("microsoft_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Microsoft",
            job_url=JOB_URL,
            config={},
            profile=ProfileData(full_name="Ada", email="a@example.com"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "first and last name" in (result.error or "")


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")
