"""Tests for the Workday apply adapter submission flow."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.workday import WorkdayApplier
from app.appliers.base import get_applier
from app.schemas.profile import ProfileData, ResumeFile
from tests.appliers.workday_helpers import JOB_URL, profile, unexpected_request
from tests.conftest import load_fixture, load_json_fixture, make_http_client


def test_dry_run_returns_payload_with_questionnaire_preview() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                answers={"q-work-auth": "Yes"},
            ),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["candidate"]["emailAddress"] == "ada@example.com"
    assert "questionnaires" in result.payload
    assert result.error is None


def test_live_submit_creates_names_questionnaires_and_finalizes() -> None:
    create_fixture = load_fixture("workday_apply_create.json")
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")
    questionnaire_response_fixture = load_json_fixture("workday_questionnaire_response.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["last_url"] = str(request.url)
        seen["last_method"] = request.method
        if request.url.path.endswith("/jobapplications"):
            seen["create_body"] = request.read().decode()
            return httpx.Response(
                200, text=create_fixture, headers={"content-type": "application/json"}
            )
        if request.url.path.endswith("/name"):
            seen["name_body"] = json.loads(request.read().decode())
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        if "questionnaireresponse" in request.url.path:
            seen["questionnaire_body"] = json.loads(request.read().decode())
            return httpx.Response(200, json=questionnaire_response_fixture)
        if request.url.path.endswith("/finalize"):
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "country_id": "US",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                answers={"q-work-auth": "Yes"},
            ),
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "app-abc123"
    assert seen["last_method"] == "POST"
    url = seen["last_url"]
    assert isinstance(url, str)
    assert url.endswith("/jobapplication/app-abc123/finalize")
    name_body = seen["name_body"]
    assert isinstance(name_body, dict)
    assert name_body["legalName"]["firstName"] == "Ada"
    questionnaire_body = seen["questionnaire_body"]
    assert isinstance(questionnaire_body, dict)
    choice_answers = questionnaire_body["questionnaireAnswers"][0]["questionMultipleChoiceAnswers"]
    assert choice_answers == ["ans-yes"]


def test_live_submit_posts_experience_and_education_before_questionnaires() -> None:
    create_fixture = load_fixture("workday_apply_create.json")
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")
    questionnaire_response_fixture = load_json_fixture("workday_questionnaire_response.json")
    order: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/jobapplications"):
            return httpx.Response(
                200, text=create_fixture, headers={"content-type": "application/json"}
            )
        if path.endswith("/name"):
            order.append("name")
            return httpx.Response(200, json={"ok": True})
        if path.endswith("/workexperiences"):
            order.append("workexperiences")
            body = json.loads(request.read().decode())
            assert body["jobTitle"] == "Engineer"
            return httpx.Response(200, json={"id": "exp-1"})
        if path.endswith("/educations"):
            order.append("educations")
            body = json.loads(request.read().decode())
            assert body["schoolName"] == "Example University"
            return httpx.Response(200, json={"id": "edu-1"})
        if path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        if "questionnaireresponse" in path:
            order.append("questionnaire")
            return httpx.Response(200, json=questionnaire_response_fixture)
        if path.endswith("/finalize"):
            order.append("finalize")
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    from app.schemas.profile import EducationEntry, WorkExperienceEntry

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                answers={"q-work-auth": "Yes"},
                work_experience=[
                    WorkExperienceEntry(
                        job_title="Engineer",
                        company="ACME",
                        start_month=1,
                        start_year=2020,
                    )
                ],
                education=[EducationEntry(school="Example University", degree="BS")],
            ),
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert order == ["name", "workexperiences", "educations", "questionnaire", "finalize"]


def test_dry_run_includes_experience_and_education_preview() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    from app.schemas.profile import EducationEntry, WorkExperienceEntry

    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                work_experience=[
                    WorkExperienceEntry(
                        job_title="Engineer",
                        company="ACME",
                        start_month=3,
                        start_year=2020,
                    )
                ],
                education=[EducationEntry(school="Example University")],
            ),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["workExperiences"][0]["companyName"] == "ACME"
    assert result.payload["educations"][0]["schoolName"] == "Example University"


def test_live_submit_uploads_resume_before_questionnaires() -> None:
    create_fixture = load_fixture("workday_apply_create.json")
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")
    questionnaire_response_fixture = load_json_fixture("workday_questionnaire_response.json")
    upload_fixture = load_json_fixture("workday_attachment_upload.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jobapplications"):
            return httpx.Response(
                200, text=create_fixture, headers={"content-type": "application/json"}
            )
        if request.url.path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/attachments"):
            seen["attachments_called"] = True
            return httpx.Response(200, json=upload_fixture)
        if request.url.path.endswith("/resumeattachments"):
            seen["resumeattachments_called"] = True
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        if "questionnaireresponse" in request.url.path:
            return httpx.Response(200, json=questionnaire_response_fixture)
        if request.url.path.endswith("/finalize"):
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=len(b"%PDF-1.4 test"),
        data=b"%PDF-1.4 test",
    )
    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                answers={"q-work-auth": "Yes"},
            ),
            resume_file=resume,
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert seen.get("attachments_called") is True
    assert seen.get("resumeattachments_called") is True
    assert result.payload is not None
    assert "resumeAttachments" in result.payload


def test_dry_run_includes_resume_attachment_preview() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                answers={"q-work-auth": "Yes"},
            ),
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["resumeAttachments"]["attachments"][0]["fileName"] == "resume.pdf"
    assert "Resume:" not in str(result.payload.get("candidate", {}).get("comments", ""))


def test_apply_fails_without_target_coordinates() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url="https://example.com/careers",
            config={},
            profile=profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "tenant" in (result.error or "").lower()


def test_apply_fails_without_job_path() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url="https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers",
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "/job/" in (result.error or "").lower()


def test_missing_csrf_token_fails_with_helpful_error() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=profile(),
            credentials={
                "cookies": {"CALYPSO_SESSION": "session-token"},
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "CSRF" in (result.error or "")
    assert result.payload is not None


def test_create_without_application_id_surfaces_workday_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jobapplications"):
            return httpx.Response(
                200,
                json={"errorCode": "AUTH_REQUIRED", "message": "Sign in required"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=profile(),
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "Sign in required"
    assert result.external_application_id is None


def test_finalize_error_returns_application_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jobapplications"):
            return httpx.Response(200, json={"id": "app-xyz", "sessionId": "sess-1"})
        if request.url.path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/finalize"):
            return httpx.Response(
                200,
                json={"errorCode": "VALIDATION_FAILED", "message": "Missing required answers"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_questionnaires": True,
            },
            profile=profile(),
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "Missing required answers"
    assert result.external_application_id == "app-xyz"


def test_missing_session_cookie_fails_with_helpful_error() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=profile(),
            credentials={
                "cookies": {},
                "headers": {},
                "session": {"csrf_token": "csrf-token"},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "CALYPSO_SESSION" in (result.error or "")
    assert result.payload is not None
