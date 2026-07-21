"""Tests for LinkedIn Easy Apply resume upload helpers."""

from __future__ import annotations

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.linkedin import LinkedInApplier
from app.appliers.adapters.linkedin_easy_apply_form import (
    build_file_upload_responses,
    extract_form_root,
    form_has_file_upload_elements,
    required_file_upload_titles,
)
from app.appliers.adapters.linkedin_resume_upload import upload_easy_apply_resume
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, load_json_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Remote",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
    )


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"li_at": "test-li-at", "JSESSIONID": "ajax:1234567890"},
        "session": {"csrf_token": "ajax:1234567890"},
        "headers": {},
    }


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )


def test_form_with_resume_fixture_has_file_upload_field() -> None:
    form = load_json_fixture("linkedin_easy_apply_form_with_resume.json")
    root = extract_form_root(form)
    assert root is not None
    assert form_has_file_upload_elements(root) is True
    assert required_file_upload_titles(root) == ["Resume"]


def test_build_file_upload_responses_maps_asset_urn() -> None:
    form = load_json_fixture("linkedin_easy_apply_form_with_resume.json")
    root = extract_form_root(form)
    assert root is not None
    responses = build_file_upload_responses(
        root,
        asset_urn="urn:li:digitalmediaAsset:C4E03AQResumeTest123",
        filename="resume.pdf",
    )
    assert len(responses) == 1
    assert responses[0]["formElementUrn"].endswith(",4,file)")
    value = responses[0]["formElementInputValues"][0]["fileUploadInputValue"]
    assert value["assetUrn"] == "urn:li:digitalmediaAsset:C4E03AQResumeTest123"
    assert value["fileName"] == "resume.pdf"


def test_upload_easy_apply_resume_posts_metadata_then_puts_file() -> None:
    metadata = load_fixture("linkedin_media_upload_resume.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "voyagerMediaUploadMetadata" in url:
            seen["metadata"] = True
            seen["metadata_cookie"] = request.headers.get("cookie", "")
            return httpx.Response(
                200,
                text=metadata,
                headers={"content-type": "application/json"},
            )
        if "ambry" in url:
            seen["upload_method"] = request.method
            seen["upload_content_type"] = request.headers.get("content-type")
            seen["upload_body"] = request.content
            seen["upload_cookie"] = request.headers.get("cookie", "")
            return httpx.Response(200, text="")
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    urn = upload_easy_apply_resume(
        make_http_client(handler),
        _resume(),
        _credentials(),
    )
    assert urn == "urn:li:digitalmediaAsset:C4E03AQResumeTest123"
    assert seen["metadata"] is True
    assert "li_at=test-li-at" in str(seen["metadata_cookie"])
    assert seen["upload_method"] == "PUT"
    assert seen["upload_content_type"] == "application/pdf"
    assert seen["upload_body"] == b"%PDF"
    # Signed Ambry URL must not receive the Voyager session jar.
    assert seen["upload_cookie"] == ""


def test_upload_easy_apply_resume_omits_cookies_on_foreign_upload_host() -> None:
    """Response-supplied upload hosts must not receive li_at."""
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "voyagerMediaUploadMetadata" in url:
            return httpx.Response(
                200,
                json={
                    "value": {
                        "singleUploadUrl": "https://evil.example/upload?sig=1",
                        "urn": "urn:li:digitalmediaAsset:C4E03AQForeignHost",
                    }
                },
            )
        if "evil.example" in url:
            seen["upload_cookie"] = request.headers.get("cookie", "")
            seen["upload_method"] = request.method
            return httpx.Response(200, text="")
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    urn = upload_easy_apply_resume(
        make_http_client(handler),
        _resume(),
        _credentials(),
    )
    assert urn == "urn:li:digitalmediaAsset:C4E03AQForeignHost"
    assert seen["upload_method"] == "PUT"
    assert seen["upload_cookie"] == ""


def test_hosted_live_submit_uploads_resume_pdf() -> None:
    viewjob = load_fixture("linkedin_job_easy_apply.html")
    form = load_fixture("linkedin_easy_apply_form_with_resume.json")
    upload_meta = load_fixture("linkedin_media_upload_resume.json")
    apply_success = load_fixture("linkedin_apply_submit_success.json")
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=viewjob)
        if "voyager/api/graphql" in url:
            return httpx.Response(
                200,
                text=form,
                headers={"content-type": "application/json"},
            )
        if "voyagerMediaUploadMetadata" in url:
            seen["upload_meta"] = True
            return httpx.Response(
                200,
                text=upload_meta,
                headers={"content-type": "application/json"},
            )
        if "ambry" in url:
            seen["ambry_upload"] = request.method
            seen["ambry_cookie"] = request.headers.get("cookie", "")
            return httpx.Response(200, text="")
        if "voyagerJobsDashOnsiteApplyApplication" in url:
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                text=apply_success,
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Quantitative Trader",
            company="Example Co",
            job_url="https://www.linkedin.com/jobs/view/quantitative-trader-at-example-co-4434410881",
            config={"accept_private_api_risk": True},
            profile=profile,
            resume_file=resume,
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert seen.get("upload_meta") is True
    assert seen.get("ambry_upload") == "PUT"
    assert seen.get("ambry_cookie") == ""
    body = seen["body"]
    assert isinstance(body, dict)
    uploads = body["fileUploadResponses"]
    assert len(uploads) == 1
    value = uploads[0]["formElementInputValues"][0]["fileUploadInputValue"]
    assert value["assetUrn"] == "urn:li:digitalmediaAsset:C4E03AQResumeTest123"
