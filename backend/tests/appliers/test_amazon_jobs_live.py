"""Tests for the Amazon Jobs apply adapter (live submit flows)."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.amazon_jobs import AmazonJobsApplier
from app.appliers.base import get_applier
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client

JOB_ID = "10410605"
JOB_URL = "https://www.amazon.jobs/en/jobs/10410605/software-development-manager-flight-software"
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
        "cookies": {"__Host-mons-sid": "session-abc", "preferred_locale": "en-US"},
        "headers": {},
        "session": {},
    }


def _resume_file() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=11,
        data=b"%PDF-1.4 test",
    )


def test_apply_returns_failed_on_http_error_during_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    applier = get_applier("amazon_jobs", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"


def test_live_submit_without_resume_skips_upload() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")
    seen: dict[str, bool] = {"upload": False}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        if path.endswith("/api/apply/applicant/"):
            return httpx.Response(200, text='{"ok": true}', headers=_JSON_HEADERS)
        if path.endswith("/api/apply/documents"):
            seen["upload"] = True
            return httpx.Response(200, text="{}", headers=_JSON_HEADERS)
        if path.endswith("/application/draft_application"):
            return httpx.Response(200, text='{"id": "d-1"}', headers=_JSON_HEADERS)
        if path.endswith("/application/submit_application"):
            return httpx.Response(200, text='{"application_id": "a-1"}', headers=_JSON_HEADERS)
        raise AssertionError(f"unexpected: {request.url}")

    applier = AmazonJobsApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert seen["upload"] is False


def test_live_submit_fails_on_applicant_update_error() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        if path.endswith("/api/apply/applicant/"):
            return httpx.Response(
                200, text='{"errors": [{"message": "bad update"}]}', headers=_JSON_HEADERS
            )
        raise AssertionError(f"unexpected: {request.url}")

    applier = AmazonJobsApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "bad update"


def test_live_submit_fails_on_resume_upload_error() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        if path.endswith("/api/apply/applicant/"):
            return httpx.Response(200, text='{"ok": true}', headers=_JSON_HEADERS)
        if path.endswith("/api/apply/documents"):
            return httpx.Response(
                200, text='{"errors": [{"message": "upload failed"}]}', headers=_JSON_HEADERS
            )
        raise AssertionError(f"unexpected: {request.url}")

    applier = AmazonJobsApplier(http=make_http_client(handler))
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=_resume_file())
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=profile,
            resume_file=_resume_file(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "upload failed"


def test_live_submit_fails_on_draft_error() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        if path.endswith("/api/apply/applicant/"):
            return httpx.Response(200, text='{"ok": true}', headers=_JSON_HEADERS)
        if path.endswith("/application/draft_application"):
            return httpx.Response(
                200, text='{"errors": [{"message": "draft bad"}]}', headers=_JSON_HEADERS
            )
        raise AssertionError(f"unexpected: {request.url}")

    applier = AmazonJobsApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "draft bad"


def test_live_submit_fails_on_submit_error() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        if path.endswith("/api/apply/applicant/"):
            return httpx.Response(200, text='{"ok": true}', headers=_JSON_HEADERS)
        if path.endswith("/application/draft_application"):
            return httpx.Response(200, text='{"id": "d-1"}', headers=_JSON_HEADERS)
        if path.endswith("/application/submit_application"):
            return httpx.Response(
                200, text='{"errors": [{"message": "submit bad"}]}', headers=_JSON_HEADERS
            )
        raise AssertionError(f"unexpected: {request.url}")

    applier = AmazonJobsApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "submit bad"


def test_live_submit_handles_http_error_during_steps() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        raise httpx.ConnectError("boom", request=request)

    applier = AmazonJobsApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None
