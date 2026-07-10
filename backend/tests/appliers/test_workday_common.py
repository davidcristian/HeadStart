"""Tests for Workday target resolution and payload builders."""

import httpx

from app.appliers.adapters.workday_common import (
    CSRF_HEADER,
    SESSION_HEADER,
    build_application_payload,
    build_http_client,
    fetch_job_posting_info,
    request_headers,
    resolve_job_path,
    resolve_job_posting_id,
    resolve_target,
)
from app.schemas.profile import ProfileData
from tests.appliers.workday_helpers import JOB_URL, profile
from tests.conftest import make_http_client


def test_resolve_target_from_config_or_url() -> None:
    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    assert target.tenant == "acme"
    assert target.site == "AcmeCareers"

    from_url = resolve_target({}, JOB_URL)
    assert from_url is not None
    assert from_url.tenant == "acme"
    assert from_url.site == "AcmeCareers"


def test_resolve_job_posting_id_from_url() -> None:
    assert resolve_job_path({}, JOB_URL) == "US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
    assert resolve_job_posting_id({}, JOB_URL, "JR1001") == "Senior-Software-Engineer_JR1001"


def test_build_application_payload_maps_profile_fields() -> None:
    payload = build_application_payload(
        profile(),
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


def test_resolve_job_posting_id_returns_none_without_inputs() -> None:
    assert resolve_job_posting_id({}, "", "") is None


def test_build_http_client_merges_credentials_and_headers() -> None:
    client = build_http_client(
        {"headers": {"X-Base": "1"}, "cookies": {"CALYPSO_SESSION": "s"}},
        headers={"X-Extra": "2"},
    )
    assert isinstance(client.close, object)
    client.close()


def test_build_http_client_handles_missing_credentials() -> None:
    client = build_http_client(None)
    client.close()


def test_fetch_job_posting_info_returns_empty_when_posting_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobPostingInfo": "not-a-dict"})

    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    assert fetch_job_posting_info(make_http_client(handler), target, "loc/job") == {}


def test_fetch_job_posting_info_returns_empty_when_response_not_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "a", "dict"])

    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    assert fetch_job_posting_info(make_http_client(handler), target, "loc/job") == {}


def test_request_headers_omits_cookie_when_empty() -> None:
    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    headers = request_headers(
        target,
        "loc/job",
        csrf_token="csrf",
        credentials={"headers": {"X-H": "1"}, "cookies": {}},
    )
    assert headers[CSRF_HEADER] == "csrf"
    assert headers["X-H"] == "1"
    assert "Cookie" not in headers


def test_request_headers_computed_win_over_stale_credential_headers() -> None:
    """Stale credential headers must not clobber CSRF / Content-Type / Referer (APL-22)."""
    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    headers = request_headers(
        target,
        "loc/job",
        csrf_token="fresh-csrf",
        session_id="fresh-session",
        credentials={
            "headers": {
                CSRF_HEADER: "stale-csrf",
                SESSION_HEADER: "stale-session",
                "Content-Type": "text/plain",
                "Referer": "https://evil.example/stale",
                "Accept": "text/html",
                "X-Custom": "keep-me",
            },
            "cookies": {"CALYPSO_SESSION": "sess"},
        },
    )
    assert headers[CSRF_HEADER] == "fresh-csrf"
    assert headers[SESSION_HEADER] == "fresh-session"
    assert headers["Content-Type"] == "application/json"
    assert headers["Referer"] == target.apply_referer("loc/job")
    assert headers["Accept"] == "application/json"
    assert headers["X-Custom"] == "keep-me"
    assert headers["Cookie"] == "CALYPSO_SESSION=sess"


def test_request_headers_multipart_drops_credential_content_type() -> None:
    """Multipart uploads must not keep a stored Content-Type (boundary is set by httpx)."""
    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    headers = request_headers(
        target,
        "loc/job",
        csrf_token="csrf",
        multipart=True,
        credentials={"headers": {"Content-Type": "application/json", "X-H": "1"}},
    )
    assert "Content-Type" not in headers
    assert headers["X-H"] == "1"
    assert headers[CSRF_HEADER] == "csrf"
