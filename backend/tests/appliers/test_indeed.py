"""Tests for the Indeed apply adapter."""

from __future__ import annotations

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.indeed import IndeedApplier
from app.appliers.adapters.indeed_detail import parse_viewjob_page, resolve_viewjob_url
from app.appliers.adapters.indeed_easy_apply import build_easy_apply_payload, build_smartapply_url
from app.appliers.adapters.indeed_route import parse_ats_job_url, resolve_apply_route
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


def test_parse_viewjob_greenhouse_fixture() -> None:
    html = load_fixture("indeed_viewjob_greenhouse.html")
    detail = parse_viewjob_page(html, fallback_job_key="fallback")
    assert detail is not None
    assert detail.job_key == "abc123def4567890"
    assert detail.external_apply_url == "https://boards.greenhouse.io/acme/jobs/5501001"
    assert detail.easily_apply is True


def test_resolve_apply_route_delegates_greenhouse() -> None:
    html = load_fixture("indeed_viewjob_greenhouse.html")
    detail = parse_viewjob_page(html)
    assert detail is not None
    route = resolve_apply_route(detail)
    assert route.kind == "external_ats"
    assert route.adapter_key == "greenhouse"
    assert route.external_id == "5501001"
    assert route.config["board_token"] == "acme"


def test_parse_ats_job_urls() -> None:
    lever = parse_ats_job_url("https://jobs.lever.co/acme/33538a2f-d27d-4a96-8f05-fa4b0e4d940e")
    assert lever is not None
    assert lever.adapter_key == "lever"
    assert lever.external_id == "33538a2f-d27d-4a96-8f05-fa4b0e4d940e"

    workday = parse_ats_job_url(
        "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/"
        "job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"
    )
    assert workday is not None
    assert workday.adapter_key == "workday"
    assert workday.external_id == "JR1001"
    assert workday.config["tenant"] == "acme"
    assert workday.config["site"] == "AcmeCareers"


def test_hosted_easy_apply_payload() -> None:
    html = load_fixture("indeed_viewjob_hosted.html")
    detail = parse_viewjob_page(html)
    assert detail is not None
    payload = build_easy_apply_payload(
        detail,
        _profile(),
        company="Hosted Co",
        job_title="Customer Support Specialist",
        cover_letter=None,
        resume_file=None,
    )
    assert payload["route"] == "indeed_hosted"
    assert payload["jobKey"] == "hostedjobkey001"
    assert payload["applicant"]["email"] == "ada@example.com"
    assert "Hosted Co" in payload["coverLetter"]
    assert "hosted-apply-id-001" in build_smartapply_url(detail)


def test_dry_run_delegates_to_greenhouse_without_live_key() -> None:
    fixture = load_fixture("indeed_viewjob_greenhouse.html")

    def handler(request: httpx.Request) -> httpx.Response:
        if "viewjob" in str(request.url):
            return httpx.Response(200, text=fixture)
        raise AssertionError(f"unexpected network call: {request.method} {request.url}")

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="abc123def4567890",
            job_title="Senior Python Developer",
            company="ACME Corp",
            job_url="https://www.indeed.com/viewjob?jk=abc123def4567890",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["indeed_route"] == "external_ats"
    assert result.payload["delegated_adapter"] == "greenhouse"
    assert result.payload["email"] == "ada@example.com"


def test_live_submit_delegates_greenhouse_post() -> None:
    viewjob = load_fixture("indeed_viewjob_greenhouse.html")
    apply_success = load_fixture("greenhouse_apply_success.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "viewjob" in url:
            return httpx.Response(200, text=viewjob)
        if "boards-api.greenhouse.io" in url:
            seen["greenhouse"] = True
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                text=apply_success,
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    applier = IndeedApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="abc123def4567890",
            job_title="Senior Python Developer",
            company="ACME Corp",
            job_url="https://www.indeed.com/viewjob?jk=abc123def4567890",
            config={"board_token": "acme", "job_board_api_key": "gh-test-key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert seen.get("greenhouse") is True
    assert result.payload is not None
    assert result.payload["delegated_adapter"] == "greenhouse"


def test_hosted_dry_run_preview() -> None:
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
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["route"] == "indeed_hosted"
    assert result.payload["jobKey"] == "hostedjobkey001"


def test_config_external_apply_url_skips_viewjob_fetch() -> None:
    applier = get_applier("indeed", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="hostedjobkey001",
            job_title="Customer Support Specialist",
            company="Hosted Co",
            job_url="https://www.indeed.com/viewjob?jk=hostedjobkey001",
            config={
                "external_apply_url": (
                    "https://smartapply.indeed.com/beta/indeedapply/applybyapplyablejobid"
                    "?indeedApplyableJobId=hosted-apply-id-001"
                )
            },
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "not a supported ATS" in (result.error or "")


def test_hosted_live_submit_posts_to_smartapply() -> None:
    viewjob = load_fixture("indeed_viewjob_hosted.html")
    apply_success = load_fixture("indeed_apply_success.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "viewjob" in url:
            return httpx.Response(200, text=viewjob)
        if "smartapply.indeed.com" in url:
            seen["method"] = request.method
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                text=apply_success,
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    applier = IndeedApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="hostedjobkey001",
            job_title="Customer Support Specialist",
            company="Hosted Co",
            job_url="https://www.indeed.com/viewjob?jk=hostedjobkey001",
            config={},
            profile=_profile(),
            credentials={
                "cookies": {"PPID": "test", "SOCK": "session"},
                "session": {"csrf_token": "csrf-1"},
                "headers": {},
            },
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "indeed-app-42"
    assert seen["method"] == "POST"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["jobKey"] == "hostedjobkey001"


def test_unsupported_external_apply_url_fails_clearly() -> None:
    fixture = load_fixture("indeed_viewjob_unsupported.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="unsupportedjob01",
            job_title="Product Designer",
            company="Beta Inc",
            job_url="https://www.indeed.com/viewjob?jk=unsupportedjob01",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "not a supported ATS" in (result.error or "")


def test_resolve_viewjob_url_builds_from_jobkey() -> None:
    url = resolve_viewjob_url("abc123", "", {"host": "www.indeed.com"})
    assert url == "https://www.indeed.com/viewjob?jk=abc123"


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
