"""Tests for Indeed apply routing to downstream ATS adapters."""

from __future__ import annotations

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.indeed_detail import parse_viewjob_page
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


def test_parse_ats_job_urls_microsoft_and_amazon() -> None:
    microsoft = parse_ats_job_url(
        "https://apply.careers.microsoft.com/careers/job/1970393556869024"
    )
    assert microsoft is not None
    assert microsoft.adapter_key == "microsoft_careers"
    assert microsoft.external_id == "1970393556869024"
    assert microsoft.config["domain"] == "microsoft.com"
    assert microsoft.config["portal_id"] == "microsoft"

    microsoft_apply = parse_ats_job_url(
        "https://apply.careers.microsoft.com/careers/apply/1970393556869024"
    )
    assert microsoft_apply is not None
    assert microsoft_apply.external_id == "1970393556869024"

    amazon = parse_ats_job_url(
        "https://www.amazon.jobs/en/jobs/10410605/software-development-manager"
    )
    assert amazon is not None
    assert amazon.adapter_key == "amazon_jobs"
    assert amazon.external_id == "10410605"
    assert amazon.config["locale"] == "en"
    assert amazon.config["portal_id"] == "amazon"

    amazon_account = parse_ats_job_url("https://account.amazon.jobs/jobs/10410605/apply")
    assert amazon_account is not None
    assert amazon_account.adapter_key == "amazon_jobs"
    assert amazon_account.external_id == "10410605"
    assert "locale" not in amazon_account.config

    meta = parse_ats_job_url("https://www.metacareers.com/jobs/2132019417725760/")
    assert meta is not None
    assert meta.adapter_key == "meta_careers"
    assert meta.external_id == "2132019417725760"
    assert meta.config["portal_id"] == "meta"


def test_resolve_apply_route_delegates_microsoft() -> None:
    html = load_fixture("indeed_viewjob_microsoft.html")
    detail = parse_viewjob_page(html)
    assert detail is not None
    route = resolve_apply_route(detail)
    assert route.kind == "external_ats"
    assert route.adapter_key == "microsoft_careers"
    assert route.external_id == "1970393556869024"
    assert route.config["domain"] == "microsoft.com"


def test_resolve_apply_route_delegates_amazon() -> None:
    html = load_fixture("indeed_viewjob_amazon.html")
    detail = parse_viewjob_page(html)
    assert detail is not None
    route = resolve_apply_route(detail)
    assert route.kind == "external_ats"
    assert route.adapter_key == "amazon_jobs"
    assert route.external_id == "10410605"
    assert route.config["locale"] == "en"


def test_dry_run_delegates_to_microsoft_without_session() -> None:
    viewjob = load_fixture("indeed_viewjob_microsoft.html")
    job_detail = load_fixture("microsoft_careers_job_detail.json")
    questions = load_fixture("microsoft_careers_questions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "viewjob" in url:
            return httpx.Response(200, text=viewjob)
        if "/api/apply/v2/jobs/" in url:
            return httpx.Response(
                200,
                text=job_detail,
                headers={"content-type": "application/json"},
            )
        if "/api/apply/v2/questions" in url:
            return httpx.Response(200, text=questions, headers={"content-type": "application/json"})
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="msftjobkey000001",
            job_title="Software Engineer",
            company="Microsoft",
            job_url="https://www.indeed.com/viewjob?jk=msftjobkey000001",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["indeed_route"] == "external_ats"
    assert result.payload["delegated_adapter"] == "microsoft_careers"
    assert result.payload["candidate"]["email"] == "ada@example.com"


def test_dry_run_delegates_to_amazon_without_session() -> None:
    viewjob = load_fixture("indeed_viewjob_amazon.html")
    search = load_fixture("amazon_jobs_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "viewjob" in url:
            return httpx.Response(200, text=viewjob)
        if "search.json" in url:
            return httpx.Response(200, text=search, headers={"content-type": "application/json"})
        raise AssertionError(f"unexpected network call: {request.method} {url}")

    applier = get_applier("indeed", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="amzjobkey0000001",
            job_title="Software Development Manager",
            company="Amazon",
            job_url="https://www.indeed.com/viewjob?jk=amzjobkey0000001",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["indeed_route"] == "external_ats"
    assert result.payload["delegated_adapter"] == "amazon_jobs"
    assert result.payload["applicant_update"]["body"]["applicant"]["email"] == "ada@example.com"
