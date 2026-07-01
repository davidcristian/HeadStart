"""Tests for the Workday apply adapter."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.workday import WorkdayApplier
from app.appliers.adapters.workday_common import (
    build_application_payload,
    resolve_job_path,
    resolve_job_posting_id,
    resolve_target,
)
from app.appliers.base import get_applier
from app.schemas.profile import ProfileData, ProfileLinks
from tests.conftest import load_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Santa Clara, CA",
        links=ProfileLinks(
            linkedin="https://linkedin.com/in/ada",
            github="https://github.com/ada",
            website="https://ada.example",
        ),
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"work_authorization": "yes"},
    )


_JOB_URL = (
    "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/"
    "job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
)


def test_resolve_target_from_config_or_url() -> None:
    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    assert target.tenant == "acme"
    assert target.site == "AcmeCareers"

    from_url = resolve_target({}, _JOB_URL)
    assert from_url is not None
    assert from_url.tenant == "acme"
    assert from_url.site == "AcmeCareers"


def test_resolve_job_posting_id_from_url() -> None:
    assert resolve_job_path({}, _JOB_URL) == "US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
    assert resolve_job_posting_id({}, _JOB_URL, "JR1001") == "Senior-Software-Engineer_JR1001"


def test_build_application_payload_maps_profile_fields() -> None:
    payload = build_application_payload(
        _profile(),
        job_posting_id="Senior-Software-Engineer_JR1001",
        job_path="US-CA-Santa-Clara/Senior-Software-Engineer_JR1001",
        job_title="Senior Software Engineer",
        company="ACME",
        config={"country_id": "US"},
    )
    assert payload["jobPostingId"] == "Senior-Software-Engineer_JR1001"
    assert payload["candidate"]["legalName"]["firstName"] == "Ada"
    assert payload["candidate"]["legalName"]["lastName"] == "Lovelace"
    assert payload["candidate"]["emailAddress"] == "ada@example.com"
    assert payload["candidate"]["phoneNumber"] == "+1 555 0100"
    assert payload["candidate"]["links"]["linkedIn"] == "https://linkedin.com/in/ada"
    assert "ACME" in payload["candidate"]["comments"]
    assert payload["answers"]["work_authorization"] == "yes"


def test_build_application_payload_requires_name_and_email() -> None:
    try:
        build_application_payload(
            ProfileData(full_name="Ada", email="ada@example.com"),
            job_posting_id="job-1",
            job_path="loc/job-1",
            job_title="Role",
            company="ACME",
            config={},
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "last name" in str(exc)


def test_dry_run_returns_payload_without_network() -> None:
    applier = get_applier("workday", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=_JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["candidate"]["emailAddress"] == "ada@example.com"
    assert result.error is None


def test_live_submit_creates_names_and_finalizes() -> None:
    create_fixture = load_fixture("workday_apply_create.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["last_url"] = str(request.url)
        seen["last_method"] = request.method
        if request.url.path.endswith("/jobapplications"):
            seen["create_body"] = request.read().decode()
            return httpx.Response(
                200, text=create_fixture, headers={"content-type": "application/json"}
            )
        if request.url.path.endswith("/name"):
            seen["name_body"] = json.loads(request.read().decode())
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/finalize"):
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=_JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5", "country_id": "US"},
            profile=_profile(),
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "app-abc123"
    assert seen["last_method"] == "POST"
    url = seen["last_url"]
    assert isinstance(url, str)
    assert url.endswith("/jobapplication/app-abc123/finalize")
    name_body = seen["name_body"]
    assert isinstance(name_body, dict)
    assert name_body["legalName"]["firstName"] == "Ada"


def test_apply_fails_without_target_coordinates() -> None:
    applier = get_applier("workday", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url="https://example.com/careers",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "tenant" in (result.error or "").lower()


def test_apply_fails_without_job_path() -> None:
    applier = get_applier("workday", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url="https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers",
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "/job/" in (result.error or "").lower()


def test_resolve_job_posting_id_returns_none_without_inputs() -> None:
    assert resolve_job_posting_id({}, "", "") is None


def test_missing_csrf_token_fails_with_helpful_error() -> None:
    applier = get_applier("workday", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=_JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=_profile(),
            credentials={
                "cookies": {"CALYPSO_SESSION": "session-token"},
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "CSRF" in (result.error or "")
    assert result.payload is not None


def test_create_without_application_id_surfaces_workday_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jobapplications"):
            return httpx.Response(
                200,
                json={"errorCode": "AUTH_REQUIRED", "message": "Sign in required"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=_JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=_profile(),
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "Sign in required"
    assert result.external_application_id is None


def test_finalize_error_returns_application_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jobapplications"):
            return httpx.Response(200, json={"id": "app-xyz", "sessionId": "sess-1"})
        if request.url.path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/finalize"):
            return httpx.Response(
                200,
                json={"errorCode": "VALIDATION_FAILED", "message": "Missing required answers"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=_JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=_profile(),
            credentials={
                "cookies": {
                    "CALYPSO_SESSION": "session-token",
                    "CALYPSO_CSRF_TOKEN": "csrf-token",
                },
                "headers": {},
                "session": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "Missing required answers"
    assert result.external_application_id == "app-xyz"


def test_missing_session_cookie_fails_with_helpful_error() -> None:
    applier = get_applier("workday", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=_JOB_URL,
            config={"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
            profile=_profile(),
            credentials={
                "cookies": {},
                "headers": {},
                "session": {"csrf_token": "csrf-token"},
            },
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "CALYPSO_SESSION" in (result.error or "")
    assert result.payload is not None


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
