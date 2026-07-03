"""Tests for the Greenhouse apply adapter."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.greenhouse import (
    GreenhouseApplier,
    basic_auth_header,
    build_application_payload,
    resolve_board_token,
    split_name,
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
        answers={"question_5555": "https://linkedin.com/in/ada"},
    )


def test_split_name() -> None:
    assert split_name("Ada Lovelace") == ("Ada", "Lovelace")
    assert split_name("Prince") == ("Prince", "")
    assert split_name("  ") == ("", "")


def test_resolve_board_token_from_config_or_url() -> None:
    assert resolve_board_token({"board_token": "acme"}, "") == "acme"
    assert resolve_board_token({}, "https://boards.greenhouse.io/acme/jobs/5501001") == "acme"
    assert resolve_board_token({}, "https://example.com/jobs/1") is None


def test_build_application_payload_maps_profile_fields() -> None:
    payload = build_application_payload(
        _profile(), job_title="Senior Engineer", company="ACME", config={"gdpr_consent": True}
    )
    assert payload["first_name"] == "Ada"
    assert payload["last_name"] == "Lovelace"
    assert payload["email"] == "ada@example.com"
    assert payload["phone"] == "+1 555 0100"
    assert payload["location"] == "London, UK"
    assert payload["resume_text"] == "Experienced engineer."
    assert "ACME" in payload["cover_letter_text"]
    assert payload["question_5555"] == "https://linkedin.com/in/ada"
    assert payload["data_compliance"]["gdpr_processing_consent_given"] is True


def test_build_application_payload_uses_cover_letter_override() -> None:
    payload = build_application_payload(
        _profile(),
        job_title="Senior Engineer",
        company="ACME",
        config={},
        cover_letter="Custom letter for ACME",
    )
    assert payload["cover_letter_text"] == "Custom letter for ACME"


def test_build_application_payload_requires_name_and_email() -> None:
    try:
        build_application_payload(
            ProfileData(full_name="Ada", email="ada@example.com"),
            job_title="Role",
            company="ACME",
            config={},
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "last name" in str(exc)


def test_build_application_payload_includes_resume_file_metadata_on_dry_run() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    payload = build_application_payload(
        profile,
        job_title="Senior Engineer",
        company="ACME",
        config={},
        include_resume_bytes=False,
    )
    assert "resume_content" not in payload
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert "resume_text" not in payload


def test_build_application_payload_attaches_resume_bytes_for_live_submit() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    payload = build_application_payload(
        profile,
        job_title="Senior Engineer",
        company="ACME",
        config={},
        include_resume_bytes=True,
    )
    assert payload["resume_content_filename"] == "resume.pdf"
    assert "resume_text" not in payload


def test_dry_run_returns_payload_without_network() -> None:
    applier = get_applier("greenhouse", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://boards.greenhouse.io/acme/jobs/5501001",
            config={"board_token": "acme"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["email"] == "ada@example.com"
    assert result.error is None


def test_live_submit_posts_json_with_basic_auth() -> None:
    fixture = load_fixture("greenhouse_apply_success.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    applier = GreenhouseApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://boards.greenhouse.io/acme/jobs/5501001",
            config={"board_token": "acme", "job_board_api_key": "gh-test-key"},
            profile=_profile(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "987654"
    assert seen["method"] == "POST"
    assert seen["url"] == ("https://boards-api.greenhouse.io/v1/boards/acme/jobs/5501001")
    assert seen["auth"] == basic_auth_header("gh-test-key")
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["first_name"] == "Ada"


def test_live_submit_prefers_credential_api_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"id": 1})

    applier = GreenhouseApplier(http=make_http_client(handler))
    applier.apply(
        ApplyContext(
            job_external_id="1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"board_token": "acme", "job_board_api_key": "config-key"},
            profile=_profile(),
            credentials={
                "session": {"job_board_api_key": "cred-key"},
                "cookies": {},
                "headers": {},
            },
            dry_run=False,
        )
    )
    assert seen["auth"] == basic_auth_header("cred-key")


def test_live_submit_treats_error_body_as_failure() -> None:
    """Regression: a 2xx whose body carries an error must fail, not report submitted."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"success": False, "errors": [{"message": "Invalid application"}]}
        )

    applier = GreenhouseApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://boards.greenhouse.io/acme/jobs/5501001",
            config={"board_token": "acme", "job_board_api_key": "gh-test-key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "Invalid application" in (result.error or "")


def test_missing_api_key_fails_with_helpful_error() -> None:
    applier = get_applier("greenhouse", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"board_token": "acme"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "Job Board API key" in (result.error or "")
    assert result.payload is not None


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
