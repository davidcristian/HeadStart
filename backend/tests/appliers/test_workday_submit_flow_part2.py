"""Error-path tests for Workday live application submission (part 2)."""

import httpx

from app.appliers.adapters.workday_common import WorkdayTarget, resolve_target
from app.appliers.adapters.workday_submit import submit_live_application
from app.appliers.adapters.workday_submit_payload import LiveSubmitProgress
from app.appliers.adapters.workday_submit_sections import (
    submit_profile_sections,
    submit_questionnaire_sections,
)
from app.schemas.profile import (
    EducationEntry,
    LanguageEntry,
    ProfileData,
    WorkExperienceEntry,
)
from tests.conftest import make_http_client

JOB_PATH = "US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
CREATE_OK = {"id": "app-abc123", "sessionId": "sess-1"}


def _target() -> WorkdayTarget:
    resolved = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert resolved is not None
    return resolved


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={"q-work-auth": "Yes"},
    )


def _submit(handler, *, profile=None, resume_file=None, config=None):
    return submit_live_application(
        make_http_client(handler),
        target=_target(),
        job_path=JOB_PATH,
        job_posting_id="Senior-Software-Engineer_JR1001",
        profile_payload={"jobPostingId": "Senior-Software-Engineer_JR1001"},
        profile=profile or _profile(),
        resume_file=resume_file,
        config=config or {"skip_questionnaires": True},
        csrf_token="csrf-token",
        credentials={"cookies": {"CALYPSO_SESSION": "s"}, "headers": {}, "session": {}},
    )


def test_auto_terms_consent_http_error_returns_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/jobapplications"):
            return httpx.Response(200, json=CREATE_OK)
        if path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if path.endswith("/termsandconditions"):
            return httpx.Response(500, text="terms failed")
        raise AssertionError(f"unexpected request: {request.url}")

    result = _submit(handler, config={"skip_questionnaires": True, "auto_terms_consent": True})
    assert result.status == "failed"
    assert result.external_application_id == "app-abc123"


def test_finalize_http_error_returns_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/jobapplications"):
            return httpx.Response(200, json=CREATE_OK)
        if path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if path.endswith("/finalize"):
            return httpx.Response(500, text="finalize failed")
        raise AssertionError(f"unexpected request: {request.url}")

    result = _submit(handler)
    assert result.status == "failed"
    assert result.external_application_id == "app-abc123"


def test_submit_profile_sections_stops_at_first_failure() -> None:
    progress = LiveSubmitProgress(profile_payload={})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/workexperiences"):
            return httpx.Response(500, text="boom")
        raise AssertionError(f"unexpected request: {request.url}")

    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(job_title="Eng", company="ACME", start_month=1, start_year=2020)
        ]
    )
    failure = submit_profile_sections(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path=JOB_PATH,
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
        progress=progress,
    )
    assert failure is not None
    assert failure.status == "failed"


def test_submit_questionnaire_sections_returns_failure() -> None:
    progress = LiveSubmitProgress(profile_payload={})
    posting = {"jobPostingInfo": {"questionnaireId": "quest-primary-001"}}
    questionnaire = {
        "questions": [{"id": "q-req", "type": {"descriptor": "Text"}, "required": True}]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/job/{JOB_PATH}"):
            return httpx.Response(200, json=posting)
        if path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire)
        raise AssertionError(f"unexpected request: {request.url}")

    failure = submit_questionnaire_sections(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=ProfileData(answers={}),
        job_path=JOB_PATH,
        config={"skip_secondary_questionnaire": True, "skip_supplementary_questionnaire": True},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
        progress=progress,
    )
    assert failure is not None
    assert failure.status == "failed"


def test_finalize_error_code_returns_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/jobapplications"):
            return httpx.Response(200, json=CREATE_OK)
        if path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if path.endswith("/finalize"):
            return httpx.Response(200, json={"errorCode": "X", "message": "rejected"})
        raise AssertionError(f"unexpected request: {request.url}")

    result = _submit(handler)
    assert result.status == "failed"
    assert result.error == "rejected"


def test_education_and_language_sections_submit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/jobapplications"):
            return httpx.Response(200, json=CREATE_OK)
        if path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if "/institutionvalues/" in path:
            return httpx.Response(200, json={"total": 0, "data": []})
        if path.endswith("/educations"):
            return httpx.Response(200, json={"id": "edu-1"})
        if path.endswith("/languages"):
            return httpx.Response(200, json={"id": "lang-1"})
        if path.endswith("/finalize"):
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected request: {request.url}")

    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        education=[EducationEntry(school="Example U", degree="BS")],
        languages=[LanguageEntry(language="English", is_native=True)],
    )
    result = _submit(handler, profile=profile)
    assert result.status == "submitted"
