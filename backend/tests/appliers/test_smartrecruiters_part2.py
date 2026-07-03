"""Tests for the SmartRecruiters apply adapter (error and edge-case paths)."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.smartrecruiters import SmartRecruitersApplier
from app.appliers.adapters.smartrecruiters_payload import extract_application_id
from app.schemas.profile import ProfileData, ProfileLinks
from tests.conftest import load_json_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(
            linkedin="https://linkedin.com/in/ada",
            website="https://ada.example",
        ),
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={
            "sr_8fe4cfaf-7d0b-4224-998b-14a3085537bb": "Yes",
            "sr_03bf8a6a-ba81-479f-8048-05ce9ef083c0": "The Analytical Engine",
        },
    )


def _handlers() -> dict[str, object]:
    posting_detail = load_json_fixture("smartrecruiters_posting_detail.json")
    configuration = load_json_fixture("smartrecruiters_apply_configuration.json")
    success = load_json_fixture("smartrecruiters_apply_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/postings/744000120624847"):
            return httpx.Response(200, json=posting_detail)
        if "/configuration" in url:
            return httpx.Response(200, json=configuration)
        if url.endswith("/candidates"):
            return httpx.Response(200, json=success)
        return httpx.Response(404, text="not found")

    return {
        "handler": handler,
        "posting_detail": posting_detail,
        "configuration": configuration,
        "success": success,
    }


def test_extract_application_id_reads_response_fields() -> None:
    assert extract_application_id({"applicationId": "app-1"}) == "app-1"
    assert extract_application_id({"id": "cand-1"}) == "cand-1"


def test_apply_without_company_id_fails() -> None:
    ctx = ApplyContext(
        job_external_id="1",
        job_title="Role",
        company="ACME",
        job_url="https://example.com/jobs/1",
        config={},
        profile=_profile(),
        dry_run=True,
    )
    result = SmartRecruitersApplier(http=make_http_client(_unexpected)).apply(ctx)
    assert result.status == "failed"
    assert "company_id" in (result.error or "")


def test_apply_fails_when_posting_uuid_resolution_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "no uuid here"})

    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=_profile(),
        dry_run=True,
    )
    result = SmartRecruitersApplier(http=make_http_client(handler)).apply(ctx)
    assert result.status == "failed"
    assert "uuid" in (result.error or "")


def test_dry_run_tolerates_configuration_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/postings/744000120624847"):
            return httpx.Response(200, json={"uuid": "uuid-1"})
        if "/configuration" in url:
            raise httpx.ConnectError("boom", request=request)
        raise AssertionError("unexpected")

    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=_profile(),
        credentials={"session": {"smart_token": "t"}},
        dry_run=True,
    )
    result = SmartRecruitersApplier(http=make_http_client(handler)).apply(ctx)
    assert result.status == "dry_run"


def test_live_submit_fails_on_configuration_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/postings/744000120624847"):
            return httpx.Response(200, json={"uuid": "uuid-1"})
        if "/configuration" in url:
            raise httpx.ConnectError("boom", request=request)
        raise AssertionError("unexpected")

    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=_profile(),
        credentials={"session": {"smart_token": "t"}},
        dry_run=False,
    )
    result = SmartRecruitersApplier(http=make_http_client(handler)).apply(ctx)
    assert result.status == "failed"


def test_apply_fails_when_payload_build_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/postings/744000120624847"):
            return httpx.Response(200, json={"uuid": "uuid-1"})
        raise AssertionError("unexpected")

    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=ProfileData(full_name="", email="a@example.com"),
        dry_run=True,
    )
    result = SmartRecruitersApplier(http=make_http_client(handler)).apply(ctx)
    assert result.status == "failed"
    assert "full_name" in (result.error or "")


def test_dry_run_builds_screening_answers_when_payload_lacks_them() -> None:
    # Configuration returns fine but candidate payload gets its answers filled in
    # from the fallback path (payload had no non-empty answers).
    fixtures = _handlers()

    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=ProfileData(full_name="Ada Lovelace", email="ada@example.com"),
        credentials={"session": {"smart_token": "t"}},
        dry_run=True,
    )
    result = SmartRecruitersApplier(http=make_http_client(fixtures["handler"])).apply(ctx)
    assert result.status == "dry_run"
    assert result.payload is not None
    assert "answers" in result.payload["candidate"]


def test_live_submit_fails_on_missing_required_answers() -> None:
    fixtures = _handlers()
    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=ProfileData(full_name="Ada Lovelace", email="ada@example.com"),
        credentials={"session": {"smart_token": "t"}},
        dry_run=False,
    )
    result = SmartRecruitersApplier(http=make_http_client(fixtures["handler"])).apply(ctx)
    assert result.status == "failed"
    assert "required screening answers" in (result.error or "")


def test_live_submit_handles_post_http_error() -> None:
    fixtures = _handlers()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/postings/744000120624847"):
            return httpx.Response(200, json=fixtures["posting_detail"])
        if "/configuration" in url:
            return httpx.Response(200, json=fixtures["configuration"])
        if url.endswith("/candidates"):
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(404, text="not found")

    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=_profile(),
        credentials={"session": {"smart_token": "t"}},
        dry_run=False,
    )
    result = SmartRecruitersApplier(http=make_http_client(handler)).apply(ctx)
    assert result.status == "failed"
    assert result.payload is not None


def test_live_submit_surfaces_api_error_message() -> None:
    fixtures = _handlers()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/postings/744000120624847"):
            return httpx.Response(200, json=fixtures["posting_detail"])
        if "/configuration" in url:
            return httpx.Response(200, json=fixtures["configuration"])
        if url.endswith("/candidates"):
            return httpx.Response(200, json={"message": "duplicate application"})
        return httpx.Response(404, text="not found")

    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Role",
        company="ACME",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=_profile(),
        credentials={"session": {"smart_token": "t"}},
        dry_run=False,
    )
    result = SmartRecruitersApplier(http=make_http_client(handler)).apply(ctx)
    assert result.status == "failed"
    assert result.error == "duplicate application"


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")
