"""Tests for the Greenhouse apply adapter (part 2)."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.greenhouse import (
    GreenhouseApplier,
    build_application_payload,
)
from app.appliers.base import get_applier
from app.schemas.profile import ProfileData
from tests.conftest import make_http_client


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


def test_apply_without_board_token_fails() -> None:
    applier = get_applier("greenhouse", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="1",
            job_title="Role",
            company="ACME",
            job_url="https://example.com/jobs/1",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "board_token" in (result.error or "")


def test_apply_skips_structured_sections_when_configured() -> None:
    applier = get_applier("greenhouse", http=make_http_client(_unexpected_request))
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        cover_letter_template="Dear team",
    )
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Role",
            company="ACME",
            job_url="https://boards.greenhouse.io/acme/jobs/5501001",
            config={
                "board_token": "acme",
                "skip_education": True,
                "skip_work_experience": True,
            },
            profile=profile,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert "employments" not in result.payload
    assert "educations" not in result.payload


def test_apply_fails_when_payload_build_raises() -> None:
    applier = get_applier("greenhouse", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Role",
            company="ACME",
            job_url="https://boards.greenhouse.io/acme/jobs/5501001",
            config={"board_token": "acme"},
            profile=ProfileData(full_name="Ada", email="ada@example.com"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "last name" in (result.error or "")


def test_build_application_payload_requires_email() -> None:
    try:
        build_application_payload(
            ProfileData(full_name="Ada Lovelace", email=""),
            job_title="Role",
            company="ACME",
            config={},
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "email" in str(exc)


def test_build_application_payload_skips_non_matching_answers() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={"question_1": "keep", "blank": "", "random_key": "drop"},
    )
    payload = build_application_payload(profile, job_title="Role", company="ACME", config={})
    assert payload["question_1"] == "keep"
    assert "blank" not in payload
    assert "random_key" not in payload


def test_live_submit_handles_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    applier = GreenhouseApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Role",
            company="ACME",
            job_url="https://boards.greenhouse.io/acme/jobs/5501001",
            config={"board_token": "acme", "job_board_api_key": "key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None


def test_resolve_api_key_falls_back_to_config() -> None:
    from app.appliers.adapters.greenhouse import resolve_api_key

    assert (
        resolve_api_key(
            {"session": {"job_board_api_key": ""}, "cookies": {}, "headers": {}},
            {"job_board_api_key": "config-key"},
        )
        == "config-key"
    )
    assert resolve_api_key(None, {}) is None


def test_extract_application_id_and_error_helpers() -> None:
    from app.appliers.adapters.greenhouse import (
        _extract_application_id,
        _extract_error_message,
        _response_has_error,
    )

    assert _extract_application_id({"application_id": "a-1"}) == "a-1"
    assert _extract_application_id({}) is None
    assert _extract_application_id("nope") is None

    assert _response_has_error("nope") is False
    assert _response_has_error({"success": True}) is False
    assert _response_has_error({"error": "boom"}) is True

    assert _extract_error_message({"error": " boom "}) == "boom"
    assert _extract_error_message({"errors": ["a", {"message": "b"}]}) == "a; b"
    assert _extract_error_message({"errors": "flat error"}) == "flat error"
    assert _extract_error_message({}) == "greenhouse apply rejected the submission"


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
