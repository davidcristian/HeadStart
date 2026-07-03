"""Tests for the Indeed apply adapter (part 2)."""

from __future__ import annotations

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.indeed import IndeedApplier
from app.appliers.adapters.indeed_detail import resolve_viewjob_url
from app.appliers.base import get_applier
from app.schemas.profile import ProfileData
from tests.conftest import load_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Remote",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
    )


def test_resolve_viewjob_url_builds_from_jobkey() -> None:
    url = resolve_viewjob_url("abc123", "", {"host": "www.indeed.com"})
    assert url == "https://www.indeed.com/viewjob?jk=abc123"


def test_apply_fails_when_viewjob_cannot_be_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>no data</html>")

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="jk-1",
            job_title="Role",
            company="ACME",
            job_url="https://www.indeed.com/viewjob?jk=jk-1",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "could not parse" in (result.error or "")


def test_config_override_delegates_to_greenhouse() -> None:
    # A pinned external_apply_url skips the viewjob fetch entirely.
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "boards-api.greenhouse.io" in url:
            return httpx.Response(
                200,
                text=load_fixture("greenhouse_apply_success.json"),
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected: {url}")

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="abc123def4567890",
            job_title="Role",
            company="ACME",
            job_url="https://www.indeed.com/viewjob?jk=abc123def4567890",
            config={
                "external_apply_url": "https://boards.greenhouse.io/acme/jobs/5501001",
                "board_token": "acme",
                "job_board_api_key": "gh-test-key",
            },
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.payload is not None
    assert result.payload["delegated_adapter"] == "greenhouse"


def test_hosted_apply_fails_when_payload_build_raises() -> None:
    fixture = load_fixture("indeed_viewjob_hosted.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="hostedjobkey001",
            job_title="Role",
            company="Hosted Co",
            job_url="https://www.indeed.com/viewjob?jk=hostedjobkey001",
            config={},
            profile=ProfileData(full_name="", email="a@example.com"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "full_name and email" in (result.error or "")


def test_hosted_live_submit_requires_session_cookies() -> None:
    fixture = load_fixture("indeed_viewjob_hosted.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="hostedjobkey001",
            job_title="Customer Support Specialist",
            company="Hosted Co",
            job_url="https://www.indeed.com/viewjob?jk=hostedjobkey001",
            config={},
            profile=_profile(),
            credentials={"cookies": {}, "session": {}, "headers": {}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "session cookies" in (result.error or "")


def test_hosted_live_submit_handles_http_error() -> None:
    viewjob = load_fixture("indeed_viewjob_hosted.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "viewjob" in url:
            return httpx.Response(200, text=viewjob)
        if "smartapply.indeed.com" in url:
            raise httpx.ConnectError("boom", request=request)
        raise AssertionError(f"unexpected: {url}")

    applier = IndeedApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="hostedjobkey001",
            job_title="Customer Support Specialist",
            company="Hosted Co",
            job_url="https://www.indeed.com/viewjob?jk=hostedjobkey001",
            config={},
            profile=_profile(),
            credentials={"cookies": {"PPID": "x"}, "session": {}, "headers": {}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None


def test_delegate_wraps_payload_none_result() -> None:
    from unittest.mock import MagicMock, patch

    from app.appliers.types import ApplyResult

    viewjob = load_fixture("indeed_viewjob_greenhouse.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=viewjob)

    delegated = MagicMock()
    delegated.apply.return_value = ApplyResult(status="failed", error="nope", payload=None)

    applier = IndeedApplier(http=make_http_client(handler))
    with patch("app.appliers.adapters.indeed.get_applier", return_value=delegated):
        result = applier.apply(
            ApplyContext(
                job_external_id="abc123def4567890",
                job_title="Role",
                company="ACME",
                job_url="https://www.indeed.com/viewjob?jk=abc123def4567890",
                config={},
                profile=_profile(),
                dry_run=True,
            )
        )
    assert result.status == "failed"
    assert result.payload is not None
    assert result.payload["delegated_payload"] is None
    assert result.payload["indeed_route"] == "external_ats"


def test_extract_application_id_and_credential_headers() -> None:
    from app.appliers.adapters.indeed import _credential_headers, _extract_application_id

    assert _extract_application_id({"application_id": "a-1"}) == "a-1"
    assert _extract_application_id({"id": "i-1"}) == "i-1"
    assert _extract_application_id({}) is None
    assert _extract_application_id("nope") is None

    assert _credential_headers(None) == {}
    assert _credential_headers({"headers": {"X": "1"}, "session": {}}) == {"X": "1"}
    headers = _credential_headers({"headers": {}, "session": {"csrf_token": "c-1"}})
    assert headers["X-Indeed-Csrf-Token"] == "c-1"
    assert headers["indeed-co"] == "US"


def test_resolve_resume_file_from_profile() -> None:
    from app.appliers.adapters.indeed import _resolve_resume_file
    from app.schemas.profile import ApplyProfile, ResumeFile

    resume = ResumeFile(
        filename="r.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    ctx_with = ApplyContext(
        job_external_id="jk",
        job_title="Role",
        company="ACME",
        job_url="",
        profile=_profile(),
        resume_file=resume,
    )
    assert _resolve_resume_file(ctx_with) is resume

    ctx_profile = ApplyContext(
        job_external_id="jk",
        job_title="Role",
        company="ACME",
        job_url="",
        profile=ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume),
    )
    assert _resolve_resume_file(ctx_profile) is not None

    ctx_none = ApplyContext(
        job_external_id="jk",
        job_title="Role",
        company="ACME",
        job_url="",
        profile=_profile(),
    )
    assert _resolve_resume_file(ctx_none) is None
