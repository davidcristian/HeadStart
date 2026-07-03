"""Tests for the Microsoft Careers apply adapter (error and live-submit paths)."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.microsoft_careers import MicrosoftCareersApplier
from app.appliers.base import get_applier
from app.schemas.profile import ProfileData
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


def test_apply_fails_on_http_error_during_fetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    applier = get_applier("microsoft_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Microsoft",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"


def test_fetch_job_detail_rejects_non_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/apply/v2/jobs/" in str(request.url):
            return httpx.Response(200, json=[1, 2, 3])
        raise AssertionError("unexpected")

    applier = get_applier("microsoft_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Microsoft",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "unexpected payload" in (result.error or "")


def test_fetch_questions_tolerates_non_dict() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/apply/v2/jobs/" in str(request.url):
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in str(request.url):
            return httpx.Response(200, json=[1, 2, 3])
        raise AssertionError("unexpected")

    applier = get_applier("microsoft_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Microsoft",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["questions"] == {}


def test_live_submit_requires_csrf_token() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/api/apply/v2/jobs/" in url:
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in url:
            return httpx.Response(200, text=questions_fixture, headers=_JSON_HEADERS)
        if "/careers/apply/" in url:
            return httpx.Response(200, text="<html>no csrf</html>")
        raise AssertionError(f"unexpected: {url}")

    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Microsoft",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            credentials={"cookies": {"_vs": "x", "_vscid": "y"}, "headers": {}, "session": {}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "CSRF token" in (result.error or "")


def test_live_submit_without_resume_skips_upload() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")
    success_fixture = load_fixture("microsoft_careers_apply_success.json")
    seen: dict[str, bool] = {"upload": False}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/api/apply/v2/jobs/" in path:
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in path:
            return httpx.Response(200, text=questions_fixture, headers=_JSON_HEADERS)
        if path.endswith("/api/apply/v2/candidate"):
            return httpx.Response(200, json={"enc_id": 1})
        if path.endswith("/api/pcsx/upload_resume"):
            seen["upload"] = True
            return httpx.Response(200, json={})
        if path.endswith("/api/application/v2/submit"):
            return httpx.Response(200, text=success_fixture, headers=_JSON_HEADERS)
        raise AssertionError(f"unexpected: {path}")

    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Microsoft",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert seen["upload"] is False


def test_live_submit_handles_http_error() -> None:
    job_fixture = load_fixture("microsoft_careers_job_detail.json")
    questions_fixture = load_fixture("microsoft_careers_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/api/apply/v2/jobs/" in path:
            return httpx.Response(200, text=job_fixture, headers=_JSON_HEADERS)
        if "/api/apply/v2/questions" in path:
            return httpx.Response(200, text=questions_fixture, headers=_JSON_HEADERS)
        if path.endswith("/api/apply/v2/candidate"):
            raise httpx.ConnectError("boom", request=request)
        raise AssertionError(f"unexpected: {path}")

    applier = MicrosoftCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Microsoft",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None
