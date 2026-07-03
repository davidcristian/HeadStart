"""Unit tests for LinkedIn Voyager lookups and resume upload metadata parsing."""

from __future__ import annotations

import httpx
import pytest

from app.appliers.adapters.linkedin_resume_upload import (
    _first_string,
    _parse_upload_metadata,
    _unwrap_value,
    upload_easy_apply_resume,
)
from app.appliers.adapters.linkedin_voyager import (
    fetch_application_form,
    fetch_company_apply_url,
    fetch_company_apply_url_via_graphql,
    fetch_company_apply_url_via_legacy,
)
from app.schemas.profile import ResumeFile
from tests.conftest import make_http_client


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"li_at": "x", "JSESSIONID": "ajax:1"},
        "session": {"csrf_token": "ajax:1"},
        "headers": {},
    }


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )


# --- resume upload metadata helpers ------------------------------------------


def test_parse_upload_metadata_rejects_non_dict() -> None:
    with pytest.raises(ValueError, match="unexpected metadata payload"):
        _parse_upload_metadata(["not", "a", "dict"])


def test_parse_upload_metadata_requires_url_and_urn() -> None:
    with pytest.raises(ValueError, match="missing upload URL or asset URN"):
        _parse_upload_metadata({"value": {"singleUploadUrl": "https://ambry"}})


def test_parse_upload_metadata_success() -> None:
    url, urn = _parse_upload_metadata(
        {"value": {"singleUploadUrl": "https://ambry/x", "urn": "urn:asset"}}
    )
    assert url == "https://ambry/x"
    assert urn == "urn:asset"


def test_unwrap_value_variants() -> None:
    assert _unwrap_value("scalar") == "scalar"
    assert _unwrap_value({"data": {"value": {"a": 1}}}) == {"a": 1}
    assert _unwrap_value({"value": {"b": 2}}) == {"b": 2}
    assert _unwrap_value({"other": 3}) == {"other": 3}


def test_first_string_skips_empty_and_returns_none() -> None:
    assert _first_string({"a": None, "b": "  "}, "a", "b") is None
    assert _first_string({"a": "val"}, "a") == "val"


def test_upload_easy_apply_resume_success_puts_file() -> None:
    session_url = "https://ambry.linkedin.test/upload/session"
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "voyagerMediaUploadMetadata" in url:
            return httpx.Response(
                200,
                json={"value": {"singleUploadUrl": session_url, "urn": "urn:asset-1"}},
                headers={"content-type": "application/json"},
            )
        if url == session_url:
            seen["method"] = request.method
            seen["content_type"] = request.headers.get("content-type")
            seen["body"] = request.content
            return httpx.Response(200, text="")
        raise AssertionError(f"unexpected {url}")

    urn = upload_easy_apply_resume(make_http_client(handler), _resume(), _credentials())
    assert urn == "urn:asset-1"
    assert seen["method"] == "PUT"
    assert seen["content_type"] == "application/pdf"
    assert seen["body"] == b"%PDF"


def test_upload_easy_apply_resume_defaults_content_type() -> None:
    session_url = "https://ambry.linkedin.test/upload/session"
    resume = ResumeFile(filename="resume.bin", content_type="   ", size_bytes=3, data=b"abc")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "voyagerMediaUploadMetadata" in url:
            return httpx.Response(
                200,
                json={"value": {"singleUploadUrl": session_url, "urn": "urn:asset-2"}},
                headers={"content-type": "application/json"},
            )
        seen["content_type"] = request.headers.get("content-type")
        return httpx.Response(200, text="")

    upload_easy_apply_resume(make_http_client(handler), resume, _credentials())
    assert seen["content_type"] == "application/octet-stream"


def test_upload_easy_apply_resume_missing_url_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"value": {"urn": "urn:asset"}},
            headers={"content-type": "application/json"},
        )

    with pytest.raises(ValueError, match="missing upload URL"):
        upload_easy_apply_resume(make_http_client(handler), _resume(), _credentials())


# --- voyager company apply url ------------------------------------------------


def test_fetch_company_apply_url_not_logged_in() -> None:
    assert fetch_company_apply_url(make_http_client(_unexpected), "1", None) is None


def test_fetch_company_apply_url_graphql_short_circuits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "voyager/api/graphql" in str(request.url)
        return httpx.Response(
            200,
            json={"companyApplyUrl": "https://ats/graphql-apply"},
            headers={"content-type": "application/json"},
        )

    result = fetch_company_apply_url(make_http_client(handler), "1", _credentials())
    assert result == "https://ats/graphql-apply"


def test_fetch_company_apply_url_via_graphql_then_legacy_fallback() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if "voyager/api/graphql" in url:
            # No companyApplyUrl -> graphql returns None, triggers legacy fallback.
            return httpx.Response(
                200, json={"data": {}}, headers={"content-type": "application/json"}
            )
        if "voyager/api/jobs/jobPostings" in url:
            return httpx.Response(
                200,
                json={"companyApplyUrl": "https://ats/apply"},
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected {url}")

    result = fetch_company_apply_url(make_http_client(handler), "1", _credentials())
    assert result == "https://ats/apply"
    assert any("graphql" in c for c in calls)
    assert any("jobPostings" in c for c in calls)


def test_fetch_company_apply_url_via_graphql_returns_decoded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"companyApplyUrl": "https://boards.greenhouse.io/acme/jobs/1"},
            headers={"content-type": "application/json"},
        )

    result = fetch_company_apply_url_via_graphql(make_http_client(handler), "1", _credentials())
    assert result == "https://boards.greenhouse.io/acme/jobs/1"


def test_fetch_company_apply_url_via_graphql_non_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=["not", "dict"], headers={"content-type": "application/json"}
        )

    assert (
        fetch_company_apply_url_via_graphql(make_http_client(handler), "1", _credentials()) is None
    )


def test_fetch_company_apply_url_via_legacy_none_when_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {}}, headers={"content-type": "application/json"})

    assert (
        fetch_company_apply_url_via_legacy(make_http_client(handler), "1", _credentials()) is None
    )


def test_fetch_company_apply_url_via_legacy_non_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json="scalar", headers={"content-type": "application/json"})

    assert (
        fetch_company_apply_url_via_legacy(make_http_client(handler), "1", _credentials()) is None
    )


# --- voyager application form -------------------------------------------------


def test_fetch_application_form_not_logged_in() -> None:
    assert fetch_application_form(make_http_client(_unexpected), "1", None) is None


def test_fetch_application_form_returns_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": {"form": 1}}, headers={"content-type": "application/json"}
        )

    result = fetch_application_form(make_http_client(handler), "1", _credentials())
    assert result == {"data": {"form": 1}}


def test_fetch_application_form_non_dict_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2], headers={"content-type": "application/json"})

    assert fetch_application_form(make_http_client(handler), "1", _credentials()) is None


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
