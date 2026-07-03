"""Tests for the Apple Careers apply adapter (part 2)."""

import json

import httpx
import pytest

from app.appliers import ApplyContext
from app.appliers.adapters import apple_careers as apple_careers_module
from app.appliers.adapters.apple_careers import AppleCareersApplier
from app.appliers.adapters.apple_careers_detail import AppleCareersJobDetail, parse_job_detail_page
from app.appliers.adapters.apple_careers_payload import (
    build_application_payload,
    build_apply_body,
    build_contact,
    build_roles,
    build_talent,
)
from app.schemas.profile import ProfileData, ResumeFile
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


def test_validate_locations_raises_for_retail_without_stores() -> None:
    detail = AppleCareersJobDetail(
        position_id="REQ-1",
        job_number="1",
        title="Retail",
        job_type="REQ",
        pipeline_type=None,
        role_location_selection=True,
        managed_pipeline_role=False,
        transformed_posting_title="retail",
        locale="en-us",
        locations=(),
    )
    with pytest.raises(ValueError, match="retail roles require"):
        apple_careers_module._validate_locations(detail, [])


def test_live_apply_requires_talent_id() -> None:
    fixture = load_fixture("apple_careers_job_detail.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = AppleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="AI Engineer",
            company="Apple",
            job_url=JOB_URL,
            config={"locale": "en-us"},
            profile=_profile(),
            credentials={"cookies": {"myacinfo": "x"}, "headers": {}, "session": {}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "talent_id" in result.error


def test_live_apply_requires_csrf_token() -> None:
    fixture = load_fixture("apple_careers_job_detail.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = AppleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="AI Engineer",
            company="Apple",
            job_url=JOB_URL,
            config={"locale": "en-us"},
            profile=_profile(),
            credentials={
                "cookies": {"myacinfo": "x", "site": "USA"},
                "headers": {},
                "session": {"talent_id": "talent-123"},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "csrf_token" in result.error


def test_live_submit_without_resume_skips_upload() -> None:
    detail_fixture = load_fixture("apple_careers_job_detail.html")
    success = json.dumps({"success": True, "data": {"applicationId": "app-777"}})
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.setdefault("paths", []).append(request.url.path)
        if request.url.path.endswith("/ai-engineer-sensing-connectivity"):
            return httpx.Response(200, text=detail_fixture)
        if request.url.path.endswith("/questionnaire"):
            return httpx.Response(200, json={"success": True, "data": {}}, headers=_JSON_HEADERS)
        if request.url.path.endswith("/applyJob"):
            return httpx.Response(200, text=success, headers=_JSON_HEADERS)
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
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "app-777"
    paths = seen["paths"]
    assert not any(str(path).endswith("/file/uploadFile") for path in paths)


def test_live_submit_fails_when_apply_job_errors() -> None:
    detail_fixture = load_fixture("apple_careers_job_detail.html")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/ai-engineer-sensing-connectivity"):
            return httpx.Response(200, text=detail_fixture)
        if request.url.path.endswith("/questionnaire"):
            return httpx.Response(200, json={"success": True, "data": {}}, headers=_JSON_HEADERS)
        if request.url.path.endswith("/applyJob"):
            return httpx.Response(403, text="denied")
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
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert result.payload is not None


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
