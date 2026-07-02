"""Tests for the Apple Careers apply adapter."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.apple_careers import AppleCareersApplier
from app.appliers.adapters.apple_careers_common import (
    extract_application_id,
    parse_details_path,
    resolve_job_detail_url,
    resolve_locale,
    resolve_talent_id,
)
from app.appliers.adapters.apple_careers_detail import parse_job_detail_page
from app.appliers.adapters.apple_careers_payload import (
    build_application_payload,
    build_apply_body,
    build_contact,
    build_roles,
    build_talent,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client

JOB_URL = (
    "https://jobs.apple.com/en-us/details/200644140-0836/"
    "ai-engineer-sensing-connectivity?team=SFTWR"
)
JOB_ID = "200644140-0836"
POSITION_ID = "REQ-200644140"
_JSON_HEADERS = {"content-type": "application/json"}


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Cupertino, CA, US",
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
    )


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"myacinfo": "session-abc", "site": "USA"},
        "headers": {},
        "session": {"talent_id": "talent-123", "csrf_token": "csrf-abc"},
    }


def test_has_applier_registers_apple_careers() -> None:
    assert has_applier("apple_careers")


def test_resolve_locale_talent_id_and_detail_url() -> None:
    assert resolve_locale({}) == "en-us"
    assert resolve_locale({"locale": "en-gb"}) == "en-gb"
    assert resolve_talent_id(_credentials(), {}) == "talent-123"
    assert resolve_talent_id(None, {"talent_id": "cfg-9"}) == "cfg-9"
    assert resolve_job_detail_url({}, JOB_URL, JOB_ID) == JOB_URL
    assert parse_details_path(JOB_URL) == (
        "en-us",
        "200644140-0836",
        "ai-engineer-sensing-connectivity",
    )


def test_parse_job_detail_fixture() -> None:
    detail = parse_job_detail_page(load_fixture("apple_careers_job_detail.html"))
    assert detail.position_id == POSITION_ID
    assert detail.title == "AI Engineer, Sensing & Connectivity"
    assert detail.job_type == "REQ"
    assert detail.role_location_selection is False
    assert len(detail.locations) == 1


def test_build_contact_maps_profile_fields() -> None:
    contact = build_contact(_profile())
    assert contact["firstName"] == "Ada"
    assert contact["lastName"] == "Lovelace"
    assert contact["preferredEmail"] == "ada@example.com"
    assert contact["preferredPhone"] == "+1 555 0100"


def test_extract_application_id() -> None:
    assert extract_application_id({"success": True, "data": {"applicationId": "app-1"}}) == "app-1"
    assert extract_application_id({"roles": {"connectionId": "conn-9"}}) == "conn-9"


def test_dry_run_fetches_job_and_returns_payload() -> None:
    fixture = load_fixture("apple_careers_job_detail.html")
    seen: dict[str, list[str]] = {"urls": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["urls"].append(str(request.url))
        if request.url.path.endswith("/ai-engineer-sensing-connectivity"):
            return httpx.Response(200, text=fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("apple_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="AI Engineer, Sensing & Connectivity",
            company="Apple",
            job_url=JOB_URL,
            config={"locale": "en-us"},
            profile=_profile(),
            dry_run=True,
        )
    )

    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["position_id"] == POSITION_ID
    assert result.payload["contact"]["preferredEmail"] == "ada@example.com"
    assert result.payload["apply_job"]["body"]["triggerType"] == "TALENT_SELF_SUBMIT"
    assert "/app/en-us/apply/REQ-200644140" in result.payload["apply_url"]
    assert any("jobs.apple.com" in url for url in seen["urls"])


def test_live_submit_puts_apply_job_with_resume_upload() -> None:
    detail_fixture = load_fixture("apple_careers_job_detail.html")
    success = json.dumps({"success": True, "data": {"applicationId": "app-555"}})
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.setdefault("paths", []).append(request.url.path)
        if request.url.path.endswith("/ai-engineer-sensing-connectivity"):
            return httpx.Response(200, text=detail_fixture)
        if request.url.path.endswith("/questionnaire"):
            return httpx.Response(
                200,
                json={"success": True, "data": {"id": "q-1"}},
                headers=_JSON_HEADERS,
            )
        if request.url.path.endswith("/file/uploadFile"):
            seen["upload"] = request.url.query.decode()
            return httpx.Response(
                200,
                json={"success": True, "data": {"fileId": "file-9", "pdfFileId": "pdf-9"}},
                headers=_JSON_HEADERS,
            )
        if request.url.path.endswith("/applyJob"):
            seen["apply_body"] = json.loads(request.content.decode())
            assert request.headers.get("X-Apple-CSRF-Token") == "csrf-abc"
            return httpx.Response(200, text=success, headers=_JSON_HEADERS)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    applier = AppleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="AI Engineer, Sensing & Connectivity",
            company="Apple",
            job_url=JOB_URL,
            config={"locale": "en-us"},
            profile=profile,
            resume_file=resume,
            credentials=_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "app-555"
    apply_body = seen["apply_body"]
    assert apply_body["roles"]["resume"]["fileId"] == "file-9"
    assert apply_body["talent"]["contact"]["preferredEmail"] == "ada@example.com"
    assert "categoryId=resume" in str(seen["upload"])


def test_live_submit_requires_session_cookies() -> None:
    detail_fixture = load_fixture("apple_careers_job_detail.html")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/ai-engineer-sensing-connectivity"):
            return httpx.Response(200, text=detail_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = AppleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="AI Engineer, Sensing & Connectivity",
            company="Apple",
            job_url=JOB_URL,
            config={"locale": "en-us"},
            profile=_profile(),
            credentials={
                "cookies": {},
                "headers": {},
                "session": {"talent_id": "t1", "csrf_token": "c1"},
            },
            dry_run=False,
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert "cookies" in result.error


def test_build_application_payload_includes_resume_metadata_on_dry_run() -> None:
    detail = parse_job_detail_page(load_fixture("apple_careers_job_detail.html"))
    contact = build_contact(_profile())
    talent = build_talent(
        _profile(),
        talent_id="talent-123",
        contact=contact,
    )
    roles = build_roles(detail, talent_id="talent-123", post_locations=[dict(detail.locations[0])])
    apply_body = build_apply_body(
        detail=detail,
        talent_id="talent-123",
        talent=talent,
        roles=roles,
    )
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    payload = build_application_payload(
        detail=detail,
        profile=_profile(),
        talent_id="talent-123",
        post_locations=[dict(detail.locations[0])],
        contact=contact,
        talent=talent,
        roles=roles,
        apply_body=apply_body,
        resume_file=resume,
    )
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert payload["resume_upload"]["url"].endswith("/file/uploadFile")
