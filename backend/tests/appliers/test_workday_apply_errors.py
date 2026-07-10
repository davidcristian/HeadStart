"""Failure-path tests for the Workday apply adapter."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.workday import WorkdayApplier
from app.appliers.base import get_applier
from app.schemas.profile import ProfileData
from tests.appliers.workday_apply_helpers import (
    JOB_URL,
    WORKDAY_CONFIG,
    WORKDAY_CREDENTIALS,
    profile,
    unexpected_request,
)
from tests.conftest import make_http_client


def test_apply_fails_without_target_coordinates() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url="https://example.com/careers",
            config={},
            profile=profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "tenant" in (result.error or "").lower()


def test_apply_fails_without_job_path() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url="https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers",
            config=WORKDAY_CONFIG,
            profile=profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "/job/" in (result.error or "").lower()


def test_missing_csrf_token_fails_with_helpful_error() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=JOB_URL,
            config=WORKDAY_CONFIG,
            profile=profile(),
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
            job_url=JOB_URL,
            config=WORKDAY_CONFIG,
            profile=profile(),
            credentials=WORKDAY_CREDENTIALS,
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
            job_url=JOB_URL,
            config={
                **WORKDAY_CONFIG,
                "skip_questionnaires": True,
            },
            profile=profile(),
            credentials=WORKDAY_CREDENTIALS,
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert result.error.startswith("Missing required answers")
    assert "app-xyz" in result.error
    assert result.external_application_id == "app-xyz"
    assert result.payload is not None
    assert result.payload.get("partial_application") is True


def test_apply_fails_when_job_posting_id_cannot_be_determined(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.appliers.adapters.workday.resolve_job_posting_id",
        lambda *args, **kwargs: None,
    )
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=JOB_URL,
            config=WORKDAY_CONFIG,
            profile=profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "job_posting_id" in (result.error or "")


def test_apply_fails_when_payload_build_raises_value_error() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=JOB_URL,
            config=WORKDAY_CONFIG,
            profile=ProfileData(full_name="Ada", email="ada@example.com"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "first and last name" in (result.error or "")


def test_live_submit_http_error_is_wrapped_as_failure() -> None:
    """An uncaught httpx error (resume multipart upload) surfaces as a failure."""
    from app.schemas.profile import ResumeFile

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/jobapplications"):
            return httpx.Response(200, json={"id": "app-1", "sessionId": "s"})
        if request.url.path.endswith("/name"):
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/attachments"):
            return httpx.Response(500, text="server error")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = WorkdayApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=JOB_URL,
            config={**WORKDAY_CONFIG, "skip_questionnaires": True},
            profile=profile(),
            resume_file=ResumeFile(
                filename="resume.pdf",
                content_type="application/pdf",
                size_bytes=4,
                data=b"%PDF",
            ),
            credentials=WORKDAY_CREDENTIALS,
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None


def test_missing_session_cookie_fails_with_helpful_error() -> None:
    applier = get_applier("workday", http=make_http_client(unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Role",
            company="ACME",
            job_url=JOB_URL,
            config=WORKDAY_CONFIG,
            profile=profile(),
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
