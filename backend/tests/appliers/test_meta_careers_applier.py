"""Flow-level tests for the Meta Careers applier covering error branches."""

from __future__ import annotations

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.meta_careers import MetaCareersApplier, _live_auth_error
from app.schemas.profile import ProfileData
from tests.conftest import load_fixture, make_http_client

JOB_ID = "2132019417725760"
JOB_URL = f"https://www.metacareers.com/jobs/{JOB_ID}/"


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+1 555 0100",
    }
    base.update(overrides)
    return ProfileData(**base)


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"c_user": "123", "xs": "abc"},
        "headers": {},
        "session": {"session_id": "session-xyz", "lsd": "csrf-token"},
    }


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")


def test_apply_value_error_from_requisition() -> None:
    applier = MetaCareersApplier(http=make_http_client(_unexpected))
    result = applier.apply(
        ApplyContext(
            job_external_id="not-a-number",
            job_title="TPM",
            company="Meta",
            job_url="https://example.com/no-match",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "requisition id" in (result.error or "")


def test_apply_http_error_on_detail_fetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # GET job page fails -> httpx.HTTPError bubbles from fetch_lsd_token.
        return httpx.Response(503, text="unavailable")

    applier = MetaCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="TPM",
            company="Meta",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"


def test_apply_live_missing_session_id() -> None:
    # Logged in cookies but no session_id -> _live_auth_error returns the session error.
    page = load_fixture("meta_careers_page.html")
    detail = load_fixture("meta_careers_job_details.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=page)
        return httpx.Response(200, text=detail, headers={"content-type": "application/json"})

    applier = MetaCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="TPM",
            company="Meta",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            credentials={"cookies": {"c_user": "1"}, "headers": {}, "session": {}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "session.session_id" in (result.error or "")


def test_apply_live_submit_error() -> None:
    page = load_fixture("meta_careers_page.html")
    detail = load_fixture("meta_careers_job_details.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=page)
        body = request.content.decode()
        if "CandidatePortalJobDetailsViewQuery" in body:
            return httpx.Response(200, text=detail, headers={"content-type": "application/json"})
        # Submit mutation returns a GraphQL error -> ValueError -> failed.
        return httpx.Response(
            200,
            json={"errors": [{"message": "submit rejected"}]},
            headers={"content-type": "application/json"},
        )

    applier = MetaCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id=JOB_ID,
            job_title="TPM",
            company="Meta",
            job_url=JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "submit rejected" in (result.error or "")
    assert result.payload is not None
    assert "submit_input" in result.payload


def test_live_auth_error_no_session_id_direct() -> None:
    result = _live_auth_error(None, None, {"k": "v"})
    assert result is not None
    assert result.status == "failed"
    assert "session.session_id" in (result.error or "")


def test_live_auth_error_ok_returns_none() -> None:
    assert _live_auth_error("sid", {"cookies": {"c_user": "1"}}, {}) is None
