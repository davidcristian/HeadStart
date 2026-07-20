"""Tests for the Rippling ATS apply adapter."""

from __future__ import annotations

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.rippling import RipplingApplier
from app.appliers.adapters.rippling_common import (
    resolve_board,
    resolve_job_id,
    turnstile_token,
)
from app.appliers.adapters.rippling_payload import (
    build_application_form_response,
    extract_application_id,
    extract_error_message,
    missing_required_fields,
    required_question_oids,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData, ProfileLinks, ResumeFile, WorkExperienceEntry
from tests.conftest import load_json_fixture, make_http_client

_JOB_ID = "2f0674e6-f01f-4ecd-b459-e947241c211f"


def _profile(*, with_resume: bool = True) -> tuple[ProfileData, ResumeFile | None]:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(
            linkedin="linkedin.com/in/ada",
            website="https://ada.example",
        ),
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="Analytical Engine Co",
                is_current=True,
            )
        ],
        answers={"country_code": "GB"},
    )
    resume = None
    if with_resume:
        resume = ResumeFile(
            filename="ada.pdf",
            content_type="application/pdf",
            size_bytes=12,
            data=b"%PDF-1.4 ada",
        )
    return profile, resume


def _handler() -> dict[str, object]:
    detail = load_json_fixture("rippling_job_detail.json")
    upload = load_json_fixture("rippling_file_upload_url.json")
    success = load_json_fixture("rippling_apply_success.json")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith(f"/jobs/{_JOB_ID}/apply") and request.method == "POST":
            assert request.headers.get("cf-client-response") == "turnstile-token"
            return httpx.Response(200, json=success)
        return httpx.Response(404, text=f"not found: {request.method} {host}{path}")

    return {
        "handler": handler,
        "calls": calls,
        "detail": detail,
        "upload": upload,
        "success": success,
    }


def test_has_applier_registers_rippling() -> None:
    assert has_applier("rippling")
    assert get_applier("rippling").__class__.__name__ == "RipplingApplier"


def test_resolve_board_and_job_id_from_config_and_url() -> None:
    assert resolve_board({"board": "rippling"}, "") == "rippling"
    assert (
        resolve_board({}, f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}") == "rippling"
    )
    assert (
        resolve_board(
            {},
            f"https://api.rippling.com/platform/api/ats/v1/board/acme/jobs/{_JOB_ID}",
        )
        == "acme"
    )
    assert resolve_board({}, "https://example.com/jobs/1") is None
    assert resolve_job_id({}, _JOB_ID, "") == _JOB_ID
    assert (
        resolve_job_id({}, "", f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}/apply")
        == _JOB_ID
    )
    assert resolve_job_id({}, "not-a-uuid", "") is None


def test_turnstile_token_from_session_or_config() -> None:
    assert turnstile_token({"session": {"cf_turnstile_token": "abc"}}, {}) == "abc"
    assert turnstile_token({"session": {"turnstile_token": "def"}}, {}) == "def"
    assert turnstile_token(None, {"cf_turnstile_token": "ghi"}) == "ghi"
    assert turnstile_token(None, {}) is None


def test_payload_helpers_map_profile_and_required_fields() -> None:
    detail = load_json_fixture("rippling_job_detail.json")
    assert isinstance(detail, dict)
    profile, resume = _profile()
    form = build_application_form_response(
        profile,
        config={},
        company="Rippling",
        cover_letter="Hello",
        resume_file=resume,
    )
    assert form["first_name"] == "Ada"
    assert form["last_name"] == "Lovelace"
    assert form["linkedin_link"] == "https://linkedin.com/in/ada"
    assert form["current_company"] == "Analytical Engine Co"
    assert form["location"] == "London"
    assert form["country_code"] == "GB"
    assert form["cover_letter_text"] == "Hello"
    assert form["resume_file"]["filename"] == "ada.pdf"

    required = required_question_oids(detail)
    assert "resume" in required
    assert "first_name" in required
    assert missing_required_fields(form, required, live=False) == []
    assert "resume" in missing_required_fields(form, required, live=True)
    assert extract_application_id({"applicationId": "app-1"}) == "app-1"
    assert extract_error_message({"error": "turnstile_verification_failure"}) == (
        "turnstile_verification_failure"
    )


def test_dry_run_builds_preview_payload() -> None:
    fixtures = _handler()
    profile, resume = _profile()
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    form = result.payload["applicationFormResponse"]
    assert form["email"] == "ada@example.com"
    assert form["resume_file"]["filename"] == "ada.pdf"
    assert "resume" not in form
    assert result.payload["job"]["required_questions"]


def test_dry_run_fails_when_required_resume_missing() -> None:
    fixtures = _handler()
    profile, _ = _profile(with_resume=False)
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "resume" in result.error


def test_live_apply_requires_turnstile_token() -> None:
    fixtures = _handler()
    profile, resume = _profile()
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "Turnstile" in result.error


def test_live_apply_uploads_resume_and_submits() -> None:
    fixtures = _handler()
    profile, resume = _profile()
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            cover_letter="Please consider my application.",
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "app-fixture-001"
    assert result.payload is not None
    form = result.payload["applicationFormResponse"]
    assert form["resume"].startswith("https://prod-rippling-us1-ats.s3.amazonaws.com/")
    assert "uploadsig=" in form["resume"]
    assert form["resumeFileExtension"] == "application/pdf"
    assert form["cover_letter"].startswith("https://")
    assert form["coverLetterFileExtension"] == "text/plain"

    methods = [request.method for request in fixtures["calls"]]  # type: ignore[index]
    assert methods.count("GET") >= 2  # job detail + upload url (+ cover upload url)
    assert "POST" in methods


def test_live_apply_reports_turnstile_failure() -> None:
    detail = load_json_fixture("rippling_job_detail.json")
    upload = load_json_fixture("rippling_file_upload_url.json")

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith("/apply"):
            return httpx.Response(401, json={"error": "turnstile_verification_failure"})
        return httpx.Response(404)

    profile, resume = _profile()
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "bad-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "turnstile_verification_failure" in result.error


def test_missing_board_fails() -> None:
    profile, resume = _profile()
    result = RipplingApplier().apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Acme",
            job_url="https://example.com/jobs/1",
            config={},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "config.board" in result.error
