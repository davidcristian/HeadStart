"""Tests for the LinkedIn apply adapter."""

from __future__ import annotations

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.linkedin import LinkedInApplier
from app.appliers.adapters.linkedin_common import resolve_job_posting_url
from app.appliers.adapters.linkedin_detail import parse_job_posting_page
from app.appliers.adapters.linkedin_easy_apply import build_easy_apply_payload
from app.appliers.adapters.linkedin_route import resolve_apply_route
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData
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


def _linkedin_credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {
            "li_at": "test-li-at",
            "JSESSIONID": "ajax:1234567890",
        },
        "session": {"csrf_token": "ajax:1234567890"},
        "headers": {},
    }


def test_has_applier_registers_linkedin() -> None:
    assert has_applier("linkedin")


def test_parse_job_posting_easy_apply_fixture() -> None:
    html = load_fixture("linkedin_job_easy_apply.html")
    detail = parse_job_posting_page(html, fallback_job_id="fallback")
    assert detail is not None
    assert detail.job_id == "4434410881"
    assert detail.easy_apply is True
    assert detail.offsite_apply is False
    assert detail.reference_id == "kTPqOWIaQcORi01GsWWTWw=="


def test_resolve_apply_route_easy_apply() -> None:
    html = load_fixture("linkedin_job_easy_apply.html")
    detail = parse_job_posting_page(html)
    assert detail is not None
    route = resolve_apply_route(detail)
    assert route.kind == "linkedin_hosted"
    assert route.adapter_key == "linkedin"


def test_hosted_easy_apply_payload() -> None:
    html = load_fixture("linkedin_job_easy_apply.html")
    detail = parse_job_posting_page(html)
    assert detail is not None
    payload = build_easy_apply_payload(
        detail,
        _profile(),
        company="Example Co",
        job_title="Quantitative Trader",
        cover_letter=None,
        resume_file=None,
    )
    assert payload["route"] == "linkedin_hosted"
    assert payload["jobId"] == "4434410881"
    assert payload["applicant"]["email"] == "ada@example.com"
    assert "Example Co" in payload["coverLetter"]


def test_dry_run_delegates_to_greenhouse_with_voyager_enrichment() -> None:
    offsite = load_fixture("linkedin_job_offsite.html")
    voyager = load_fixture("linkedin_voyager_job_greenhouse.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=offsite)
        if "voyager/api/graphql" in url:
            return httpx.Response(
                200,
                text=voyager,
                headers={"content-type": "application/json"},
            )
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    applier = get_applier("linkedin", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4432008529",
            job_title="Python Developer",
            company="CGI",
            job_url="https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529",
            config={"board_token": "acme"},
            profile=_profile(),
            credentials=_linkedin_credentials(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["linkedin_route"] == "external_ats"
    assert result.payload["delegated_adapter"] == "greenhouse"
    assert result.payload["email"] == "ada@example.com"


def test_hosted_dry_run_preview() -> None:
    fixture = load_fixture("linkedin_job_easy_apply.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = get_applier("linkedin", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Quantitative Trader",
            company="Example Co",
            job_url="https://www.linkedin.com/jobs/view/quantitative-trader-at-example-co-4434410881",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["route"] == "linkedin_hosted"
    assert result.payload["jobId"] == "4434410881"


def test_config_external_apply_url_skips_guest_fetch() -> None:
    applier = get_applier("linkedin", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="4432008529",
            job_title="Python Developer",
            company="CGI",
            job_url="https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529",
            config={"external_apply_url": "https://boards.greenhouse.io/acme/jobs/5501001"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["linkedin_route"] == "external_ats"
    assert result.payload["delegated_adapter"] == "greenhouse"


def test_offsite_without_external_url_fails_clearly() -> None:
    fixture = load_fixture("linkedin_job_offsite.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = get_applier("linkedin", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4432008529",
            job_title="Python Developer",
            company="CGI",
            job_url="https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "offsite apply URL was not found" in (result.error or "")


def test_hosted_live_submit_posts_to_voyager() -> None:
    viewjob = load_fixture("linkedin_job_easy_apply.html")
    form = load_fixture("linkedin_easy_apply_form_simple.json")
    apply_success = load_fixture("linkedin_apply_submit_success.json")
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
        if "voyager/api/jobs/jobPostings" in url:
            return httpx.Response(
                200,
                text="{}",
                headers={"content-type": "application/json"},
            )
        if "voyagerJobsDashOnsiteApplyApplication" in url:
            seen["method"] = request.method
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
            profile=_profile(),
            credentials=_linkedin_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "linkedin-app-99"
    assert seen["method"] == "POST"
    body = seen["body"]
    assert isinstance(body, dict)
    assert isinstance(body["responses"], list)
    assert len(body["responses"]) == 3


def test_hosted_live_submit_requires_private_api_risk_ack() -> None:
    """APL-17: Voyager live submit needs explicit ToS/ban-risk consent."""
    viewjob = load_fixture("linkedin_job_easy_apply.html")
    form = load_fixture("linkedin_easy_apply_form_simple.json")

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
        if "voyager/api/jobs/jobPostings" in url:
            return httpx.Response(
                200,
                text="{}",
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
            config={},
            profile=_profile(),
            credentials=_linkedin_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "accept_private_api_risk" in (result.error or "")
    assert "Terms of Service" in (result.error or "")


def test_hosted_live_submit_fails_on_2xx_error_body() -> None:
    """APL-16: Voyager 200 with errors must not report submitted."""
    viewjob = load_fixture("linkedin_job_easy_apply.html")
    form = load_fixture("linkedin_easy_apply_form_simple.json")

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
        if "voyager/api/jobs/jobPostings" in url:
            return httpx.Response(
                200,
                text="{}",
                headers={"content-type": "application/json"},
            )
        if "voyagerJobsDashOnsiteApplyApplication" in url:
            return httpx.Response(
                200,
                json={"errors": [{"message": "Already applied"}]},
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
            profile=_profile(),
            credentials=_linkedin_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "Already applied"
    assert result.external_application_id is None
    assert result.payload is not None


def test_resolve_job_posting_url_builds_guest_api_url() -> None:
    url = resolve_job_posting_url("4434410881", "")
    assert url == "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4434410881"


def test_decode_linkedin_redirect_fixture_company_apply_url() -> None:
    voyager = load_json_fixture("linkedin_voyager_job_greenhouse.json")
    assert isinstance(voyager, dict)
    detail = parse_job_posting_page(load_fixture("linkedin_job_offsite.html"))
    assert detail is not None
    route = resolve_apply_route(detail)
    assert route.kind == "unsupported"
    from app.appliers.adapters.linkedin_detail import extract_company_apply_url

    external = extract_company_apply_url(voyager)
    assert external == "https://boards.greenhouse.io/acme/jobs/5501001"


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
