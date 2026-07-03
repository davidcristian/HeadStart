"""Tests for the Ashby apply adapter (apply/network flows)."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.ashby import (
    AshbyApplier,
    basic_auth_header,
)
from app.appliers.base import get_applier
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"custom_question_path": "Yes"},
    )


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")


def test_dry_run_returns_payload_without_network() -> None:
    applier = get_applier("ashby", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="7458d4e9-da2e-47bd-98cb-adfda43d42b2",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://jobs.ashbyhq.com/acme/7458d4e9-da2e-47bd-98cb-adfda43d42b2",
            config={"board": "acme"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["jobPostingId"] == "7458d4e9-da2e-47bd-98cb-adfda43d42b2"
    assert result.error is None


def test_live_submit_posts_json_with_basic_auth() -> None:
    fixture = load_fixture("ashby_apply_success.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    applier = AshbyApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="7458d4e9-da2e-47bd-98cb-adfda43d42b2",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://jobs.ashbyhq.com/acme/7458d4e9-da2e-47bd-98cb-adfda43d42b2",
            config={"board": "acme", "ashby_api_key": "ashby-test-key"},
            profile=_profile(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    assert seen["method"] == "POST"
    assert seen["url"] == "https://api.ashbyhq.com/applicationForm.submit"
    assert seen["auth"] == basic_auth_header("ashby-test-key")
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["jobPostingId"] == "7458d4e9-da2e-47bd-98cb-adfda43d42b2"


def test_live_submit_prefers_credential_api_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(
            200,
            json={
                "success": True,
                "results": {
                    "submittedFormInstance": {"id": "app-1"},
                    "formMessages": {"blocked": False},
                },
            },
        )

    applier = AshbyApplier(http=make_http_client(handler))
    applier.apply(
        ApplyContext(
            job_external_id="job-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"board": "acme", "ashby_api_key": "config-key"},
            profile=_profile(),
            credentials={
                "session": {"ashby_api_key": "cred-key"},
                "cookies": {},
                "headers": {},
            },
            dry_run=False,
        )
    )
    assert seen["auth"] == basic_auth_header("cred-key")


def test_live_submit_surfaces_api_error_response() -> None:
    applier = AshbyApplier(
        http=make_http_client(
            lambda _request: httpx.Response(
                200,
                json={
                    "success": False,
                    "errors": ["validation_failed"],
                    "errorInfo": {"message": "Email is invalid"},
                },
            )
        )
    )
    result = applier.apply(
        ApplyContext(
            job_external_id="job-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"board": "acme", "ashby_api_key": "key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "Email is invalid"


def test_missing_api_key_fails_with_helpful_error() -> None:
    applier = get_applier("ashby", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="job-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"board": "acme"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "API key" in (result.error or "")
    assert result.payload is not None


def test_apply_returns_failed_when_payload_build_raises() -> None:
    applier = get_applier("ashby", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="job-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={},
            profile=ProfileData(full_name="", email="ada@example.com"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "full_name" in (result.error or "")


def test_live_submit_posts_multipart_when_resume_present() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content_type"] = request.headers.get("content-type", "")
        return httpx.Response(
            200,
            json={"success": True, "results": {"submittedFormInstance": {"id": "app-9"}}},
        )

    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=_resume())
    applier = AshbyApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="job-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"ashby_api_key": "key"},
            profile=profile,
            resume_file=_resume(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "app-9"
    assert "multipart/form-data" in str(seen["content_type"])


def test_live_submit_handles_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    applier = AshbyApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="job-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"ashby_api_key": "key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None


def test_live_submit_surfaces_blocked_message() -> None:
    applier = AshbyApplier(
        http=make_http_client(
            lambda _request: httpx.Response(
                200,
                json={
                    "success": True,
                    "results": {
                        "formMessages": {
                            "blocked": True,
                            "blockMessageForCandidateHtml": "You already applied",
                        }
                    },
                },
            )
        )
    )
    result = applier.apply(
        ApplyContext(
            job_external_id="job-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"ashby_api_key": "key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "You already applied"
