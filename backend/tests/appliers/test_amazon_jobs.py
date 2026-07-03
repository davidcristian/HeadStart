"""Tests for the Amazon Jobs apply adapter."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.amazon_jobs import AmazonJobsApplier
from app.appliers.adapters.amazon_jobs_common import (
    extract_application_id,
    resolve_job_id,
    resolve_locale,
)
from app.appliers.adapters.amazon_jobs_payload import (
    build_applicant_body,
    build_application_payload,
)
from app.appliers.base import get_applier, has_applier
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


def test_has_applier_registers_amazon_jobs() -> None:
    assert has_applier("amazon_jobs")


def test_resolve_job_id_and_locale() -> None:
    assert resolve_locale({}) == "en"
    assert resolve_locale({"locale": "de"}) == "de"
    assert resolve_job_id({}, JOB_URL, JOB_ID) == JOB_ID
    assert resolve_job_id({"job_id": "999"}, "", "fallback") == "999"


def test_build_applicant_body_maps_profile_fields() -> None:
    body = build_applicant_body(
        _profile(),
        company="Amazon",
        job_title="Software Development Manager",
    )
    applicant = body["applicant"]
    assert applicant["legal_first_name"] == "Ada"
    assert applicant["legal_last_name"] == "Lovelace"
    assert applicant["email"] == "ada@example.com"
    assert applicant["primary_phone_number"] == "+1 555 0100"
    assert applicant["work_authorization"] == "Yes"


def test_extract_application_id() -> None:
    assert extract_application_id({"application_id": "app-1"}) == "app-1"
    assert extract_application_id({"data": {"id": 42}}) == "42"
    assert extract_application_id({"application": {"id": "disp-9"}}) == "disp-9"


def test_dry_run_fetches_job_and_returns_payload() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")
    seen: dict[str, list[str]] = {"urls": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["urls"].append(str(request.url))
        if request.url.path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("amazon_jobs", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Development Manager, Flight Software",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            dry_run=True,
        )
    )

    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["job"]["job_id"] == JOB_ID
    assert result.payload["applicant_update"]["body"]["applicant"]["email"] == "ada@example.com"
    assert "10410605/apply" in result.payload["job"]["apply_url"]
    assert any("/search.json" in url for url in seen["urls"])


def test_live_submit_updates_applicant_drafts_and_submits() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")
    success = json.dumps({"application_id": "app-555"})
    seen: dict[str, object] = {"paths": []}

    def handler(request: httpx.Request) -> httpx.Response:
        paths = seen.setdefault("paths", [])
        assert isinstance(paths, list)
        paths.append(request.url.path)
        if request.url.path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        if request.url.path.endswith("/api/apply/applicant/"):
            seen["applicant_body"] = json.loads(request.content.decode())
            assert request.method == "PUT"
            return httpx.Response(200, text='{"ok": true}', headers=_JSON_HEADERS)
        if request.url.path.endswith("/api/apply/documents"):
            seen["resume_upload"] = True
            return httpx.Response(200, text='{"id": "doc-1"}', headers=_JSON_HEADERS)
        if request.url.path.endswith("/application/draft_application"):
            seen["draft_body"] = json.loads(request.content.decode())
            return httpx.Response(200, text='{"disposition_id": "disp-1"}', headers=_JSON_HEADERS)
        if request.url.path.endswith("/application/submit_application"):
            return httpx.Response(200, text=success, headers=_JSON_HEADERS)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = AmazonJobsApplier(http=make_http_client(handler))
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=_resume_file())
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Development Manager, Flight Software",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en", "recruiting_source": "external"},
            profile=profile,
            resume_file=_resume_file(),
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "app-555"
    assert seen["resume_upload"] is True
    assert seen["draft_body"] == {"recruiting_source": "external"}
    applicant_body = seen["applicant_body"]
    assert isinstance(applicant_body, dict)
    assert applicant_body["applicant"]["email"] == "ada@example.com"


def test_live_submit_requires_session_cookies() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("amazon_jobs", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Software Development Manager, Flight Software",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=_profile(),
            credentials={"cookies": {}, "headers": {}, "session": {}},
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.payload is not None
    assert "session cookies" in (result.error or "")


def test_build_application_payload_includes_resume_metadata() -> None:
    from app.appliers.adapters.amazon_jobs_detail import AmazonJobDetail

    detail = AmazonJobDetail(
        job_id=JOB_ID,
        title="Software Development Manager, Flight Software",
        company="Amazon",
        location="Redmond, Washington, USA",
        country_code="USA",
        apply_url="https://www.amazon.jobs/applicant/jobs/10410605/apply",
        account_apply_url="https://account.amazon.jobs/jobs/10410605/apply",
        raw={},
    )
    payload = build_application_payload(
        detail,
        ApplyProfile(**_profile().model_dump(), exists=True, resume_file=_resume_file()),
        company="Amazon",
        job_title="Software Development Manager, Flight Software",
        resume_file=_resume_file(),
    )
    assert payload["resume_upload"]["filename"] == "resume.pdf"


def test_apply_without_job_id_fails() -> None:
    applier = get_applier("amazon_jobs", http=make_http_client(_unexpected))
    result = applier.apply(
        ApplyContext(
            job_external_id="",
            job_title="Role",
            company="Amazon",
            job_url="https://www.amazon.jobs/en/teams",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "job id" in (result.error or "")


def test_apply_returns_failed_on_value_error() -> None:
    fixture = load_fixture("amazon_jobs_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search.json"):
            return httpx.Response(200, text=fixture, headers=_JSON_HEADERS)
        raise AssertionError("unexpected")

    applier = get_applier("amazon_jobs", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="Role",
            company="Amazon",
            job_url=JOB_URL,
            config={"locale": "en"},
            profile=ProfileData(full_name="", email="ada@example.com"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "full_name" in (result.error or "")


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")
