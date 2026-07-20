"""Tests for the Phenom People apply adapter."""

from __future__ import annotations

import json

import httpx
import pytest

from app.appliers import ApplyContext
from app.appliers.adapters.phenom_common import (
    extract_application_id,
    extract_error_message,
    resolve_access_token,
    resolve_careers_base_url,
    resolve_country,
    resolve_external_apply_url,
    resolve_job_id,
    resolve_locale,
    resolve_ref_num,
)
from app.appliers.adapters.phenom_detail import (
    detail_from_job,
    detail_from_override,
    job_from_detail_response,
)
from app.appliers.adapters.phenom_payload import (
    build_application_payload,
    custom_fields_from_answers,
)
from app.appliers.adapters.phenom_route import resolve_apply_route
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData, ProfileLinks, ResumeFile, WorkExperienceEntry
from tests.conftest import load_json_fixture, make_http_client

_JOB_ID = "CISCISGLOBAL2015573EXTERNALENGLOBAL"
_SESSION_HTML = """
<html><script>
var phApp = {"refNum":"CISCISGLOBAL","csrfToken":"test-csrf"};
</script></html>
"""


def _profile(*, with_resume: bool = False) -> tuple[ProfileData, ResumeFile | None]:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+15550100",
        location="London, UK",
        links=ProfileLinks(linkedin="linkedin.com/in/ada"),
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="Analytical Engines",
                location="London",
                start_month=1,
                start_year=2020,
                is_current=True,
                description="Built engines.",
            )
        ],
        answers={"phenom_workAuth": "Yes"},
    )
    resume = None
    if with_resume:
        resume = ResumeFile(
            filename="ada.pdf",
            content_type="application/pdf",
            size_bytes=12,
            data=b"%PDF-1.4 ada",
        )
    return profile, resume


def _ctx(
    *,
    dry_run: bool = True,
    job_url: str = f"https://careers.cisco.com/global/en/job/{_JOB_ID}",
    config: dict | None = None,
    credentials: dict | None = None,
    with_resume: bool = False,
) -> ApplyContext:
    profile, resume = _profile(with_resume=with_resume)
    return ApplyContext(
        job_external_id=_JOB_ID,
        job_title="Customer Success Splunk Platform Area TAM",
        company="Splunk",
        job_url=job_url,
        config=config
        or {
            "careers_base_url": "https://careers.cisco.com",
            "country": "global",
            "locale": "en_global",
            "ref_num": "CISCISGLOBAL",
            "company": "Splunk",
        },
        profile=profile,
        resume_file=resume,
        credentials=credentials,
        dry_run=dry_run,
    )


def _widgets_handler(
    detail: object,
    *,
    fail_detail: bool = False,
    apply_posts: list[httpx.Request] | None = None,
    apply_response: httpx.Response | None = None,
):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if request.method == "GET" and "search-results" in path:
            return httpx.Response(200, text=_SESSION_HTML)
        if request.method == "POST" and path.endswith("/widgets"):
            body = json.loads(request.content.decode())
            assert body["ddoKey"] == "jobDetail"
            assert request.headers.get("x-csrf-token") == "test-csrf"
            if fail_detail:
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(200, json=detail)
        if (
            apply_posts is not None
            and request.method == "POST"
            and path.endswith("/apply/v2/applications")
        ):
            apply_posts.append(request)
            assert request.headers.get("Authorization", "").startswith("Bearer ")
            if apply_response is not None:
                return apply_response
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "statusCode": "200",
                    "data": {"applicationId": "app-99"},
                },
            )
        # Downstream Workday dry-run probes CXS / Calypso; return empty metadata.
        if "myworkdayjobs.com" in host:
            return httpx.Response(200, json={"jobPostingInfo": {}})
        raise AssertionError(f"unexpected request: {request.method} {host}{path}")

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


def test_has_applier_phenom() -> None:
    assert has_applier("phenom")


def test_resolve_helpers() -> None:
    assert (
        resolve_careers_base_url({}, "https://careers.cisco.com/global/en/job/x")
        == "https://careers.cisco.com"
    )
    assert resolve_careers_base_url({}, "not-a-url") is None
    assert resolve_country({"country": "CA"}, "") == "ca"
    assert resolve_country({}, "https://careers.cisco.com/global/en/job/x") == "global"
    assert resolve_locale({}, "https://careers.cisco.com/global/en/job/x") == "en_global"
    assert resolve_locale({}, "https://careers.cisco.com/us/en_us/job/x") == "en_us"
    assert resolve_ref_num({"refNum": "ABC"}, None) == "ABC"
    assert resolve_ref_num({}, {"session": {"ref_num": "XYZ"}}) == "XYZ"
    assert resolve_job_id({}, "", f"https://careers.cisco.com/us/en/job/{_JOB_ID}") == _JOB_ID
    assert resolve_job_id({"job_id": "99"}, "", "") == "99"
    assert resolve_external_apply_url({"applyUrl": "https://example.com/a"}) == (
        "https://example.com/a"
    )
    assert resolve_access_token({"session": {"access_token": "tok"}}, {}) == "tok"
    assert extract_error_message({"statusMessage": "nope"}) == "nope"
    assert extract_error_message({"errors": [{"message": "bad"}]}) == "bad"
    assert extract_application_id({"data": {"applicationId": "a1"}}) == "a1"


def test_job_from_detail_response() -> None:
    detail = job_from_detail_response(load_json_fixture("phenom_job_detail.json"))
    assert detail is not None
    assert detail.job_id == _JOB_ID
    assert detail.apply_url is not None
    assert "myworkdayjobs.com" in detail.apply_url
    assert job_from_detail_response({"jobDetail": {}}) is None
    assert detail_from_job({}) is None
    override = detail_from_override(job_id="1", title="T", apply_url="https://x")
    assert override.external_apply is True


def test_resolve_apply_route_delegates_workday() -> None:
    detail = job_from_detail_response(load_json_fixture("phenom_job_detail.json"))
    assert detail is not None
    route = resolve_apply_route(detail, careers_base_url="https://careers.cisco.com")
    assert route.kind == "external_ats"
    assert route.adapter_key == "workday"
    assert route.external_id == "2015573-1"
    assert route.config["tenant"] == "cisco"
    assert route.config["site"] == "Cisco_Careers"


def test_resolve_apply_route_hosted_and_unsupported() -> None:
    hosted = job_from_detail_response(load_json_fixture("phenom_job_detail_hosted.json"))
    assert hosted is not None
    route = resolve_apply_route(hosted)
    assert route.kind == "phenom_hosted"

    same_host = detail_from_override(
        job_id="1",
        title="T",
        apply_url="https://careers.cisco.com/global/en/apply/1",
    )
    assert (
        resolve_apply_route(same_host, careers_base_url="https://careers.cisco.com").kind
        == "phenom_hosted"
    )

    unknown = detail_from_override(
        job_id="1",
        title="T",
        apply_url="https://example.com/apply/secret",
    )
    bad = resolve_apply_route(unknown, careers_base_url="https://careers.cisco.com")
    assert bad.kind == "unsupported"


def test_build_application_payload() -> None:
    profile, resume = _profile(with_resume=True)
    payload = build_application_payload(
        profile,
        job_id=_JOB_ID,
        resume_file=resume,
        include_resume_bytes=False,
        custom_fields=custom_fields_from_answers(profile.answers),
    )
    assert payload["candidateData"]["firstName"] == "Ada"
    assert payload["jobApplicationData"]["jobId"] == _JOB_ID[:50]
    assert payload["customFieldData"]["workAuth"] == "Yes"
    assert "fileContent" not in payload["resumeData"]
    live = build_application_payload(
        profile, job_id=_JOB_ID, resume_file=resume, include_resume_bytes=True
    )
    assert "fileContent" in live["resumeData"]


def test_dry_run_delegates_to_workday() -> None:
    detail = load_json_fixture("phenom_job_detail.json")
    handler = _widgets_handler(detail)
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(_ctx(dry_run=True))
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["phenom_route"] == "external_ats"
    assert result.payload["delegated_adapter"] == "workday"
    assert result.payload["phenom_job_id"] == _JOB_ID


def test_config_apply_url_skips_widgets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        if "myworkdayjobs.com" in host:
            return httpx.Response(200, json={"jobPostingInfo": {}})
        raise AssertionError(f"unexpected network: {request.url}")

    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=True,
            config={
                "apply_url": (
                    "https://cisco.wd5.myworkdayjobs.com/Cisco_Careers/job/"
                    "Richardson-Texas-US/Customer-Success-Splunk-Platform-Area-TAM_2015573-1/apply"
                ),
            },
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["delegated_adapter"] == "workday"


def test_missing_job_id_fails() -> None:
    applier = get_applier("phenom", http=make_http_client(lambda r: httpx.Response(500)))
    result = applier.apply(
        ApplyContext(
            job_external_id="",
            job_title="T",
            company="C",
            job_url="https://careers.cisco.com/",
            config={"careers_base_url": "https://careers.cisco.com"},
            profile=_profile()[0],
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "job id" in result.error


def test_job_detail_missing_job_object() -> None:
    handler = _widgets_handler({}, fail_detail=True)
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(_ctx(dry_run=True))
    assert result.status == "failed"
    assert result.error is not None
    assert "job object" in result.error


def _hosted_config() -> dict:
    return {
        "careers_base_url": "https://careers.cisco.com",
        "country": "us",
        "locale": "en_us",
        "ref_num": "ACMEGLOBAL",
    }


def test_hosted_dry_run() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")
    handler = _widgets_handler(detail)
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=True,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config=_hosted_config(),
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["phenom_route"] == "phenom_hosted"
    assert result.payload["application"]["candidateData"]["contactData"]["email"] == (
        "ada@example.com"
    )


def test_hosted_live_requires_token() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")
    handler = _widgets_handler(detail)
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=False,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config=_hosted_config(),
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "access_token" in result.error


def test_hosted_live_submit() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")
    apply_posts: list[httpx.Request] = []
    handler = _widgets_handler(detail, apply_posts=apply_posts)
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=False,
            with_resume=True,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config={**_hosted_config(), "phenom_apply_api_base": "https://api.phenompro.com"},
            credentials={"session": {"access_token": "secret-token"}},
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "app-99"
    assert len(apply_posts) == 1
    body = json.loads(apply_posts[0].content.decode())
    assert "fileContent" in body["resumeData"]


def test_hosted_live_api_error() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")
    apply_posts: list[httpx.Request] = []
    handler = _widgets_handler(
        detail,
        apply_posts=apply_posts,
        apply_response=httpx.Response(
            400,
            json={"status": "error", "statusMessage": "invalid job"},
        ),
    )
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=False,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config=_hosted_config(),
            credentials={"session": {"bearer_token": "tok"}},
        )
    )
    assert result.status == "failed"
    assert result.error == "invalid job"


def test_unsupported_external_apply_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no network")

    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=True,
            config={
                "careers_base_url": "https://careers.cisco.com",
                "apply_url": "https://unknown-ats.example/jobs/1/apply",
            },
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "not a supported ATS" in result.error


def test_payload_requires_name_and_email() -> None:
    profile = ProfileData(full_name="", email="")
    try:
        build_application_payload(profile, job_id="1")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "full_name" in str(exc)


def test_missing_careers_base_without_apply_url() -> None:
    applier = get_applier("phenom", http=make_http_client(lambda r: httpx.Response(500)))
    result = applier.apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="T",
            company="C",
            job_url="",
            config={},
            profile=_profile()[0],
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "careers_base_url" in result.error


def test_widgets_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "search-results" in str(request.url):
            return httpx.Response(200, text=_SESSION_HTML)
        return httpx.Response(503, text="down")

    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(_ctx(dry_run=True))
    assert result.status == "failed"
    assert result.error is not None


def test_job_detail_non_dict_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "search-results" in str(request.url):
            return httpx.Response(200, text=_SESSION_HTML)
        if request.method == "POST":
            return httpx.Response(200, json=["not", "an", "object"])
        raise AssertionError(str(request.url))

    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(_ctx(dry_run=True))
    assert result.status == "failed"
    assert result.error is not None
    assert "unexpected payload" in result.error


def test_detail_parsers_edge_cases() -> None:
    assert job_from_detail_response("nope") is None
    nested = {
        "jobDetail": {
            "job": {
                "jobSeqNo": "J1",
                "title": "T",
                "apply_url": "https://boards.greenhouse.io/acme/jobs/1",
            }
        }
    }
    detail = job_from_detail_response(nested)
    assert detail is not None
    assert detail.apply_url is not None


def test_route_unsupported_ats_without_applier(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.appliers.adapters import phenom_route
    from app.appliers.adapters.indeed_route import AtsJobTarget

    monkeypatch.setattr(
        phenom_route,
        "parse_ats_job_url",
        lambda url: AtsJobTarget(
            adapter_key="no_such_applier",
            external_id="1",
            job_url=url,
            config={},
        ),
    )
    monkeypatch.setattr(phenom_route, "has_applier", lambda key: False)
    detail = detail_from_override(job_id="1", title="T", apply_url="https://example.com/x")
    route = resolve_apply_route(detail)
    assert route.kind == "unsupported"
    assert route.adapter_key == "no_such_applier"


def test_common_helpers_defaults_and_errors() -> None:
    from app.appliers.adapters.phenom_common import (
        applications_url,
        apply_api_base,
        extract_application_id,
        extract_error_message,
        parse_session_html,
        resolve_country,
        resolve_locale,
        search_results_url,
    )

    assert resolve_country({}, "") == "us"
    assert resolve_locale({}, "") == "en_us"
    assert apply_api_base({"apply_api_base": "https://api.example.com/"}) == (
        "https://api.example.com"
    )
    assert applications_url({}).endswith("/apply/v2/applications")
    assert parse_session_html("<html></html>") == (None, "")
    assert extract_error_message(" plain ") == "plain"
    assert extract_error_message({"errors": ["boom"]}) == "boom"
    assert extract_error_message(None) is None
    assert extract_application_id({"applicationId": "z"}) == "z"
    assert extract_application_id("x") is None
    assert "us/en/search-results" in search_results_url("https://careers.cisco.com", "us", "en_us")


def test_payload_experience_variants() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            WorkExperienceEntry(job_title="", company="X"),
            WorkExperienceEntry(
                job_title="Eng",
                company="Y",
                start_year=2019,
                end_year=2020,
            ),
            WorkExperienceEntry(
                job_title="Lead",
                company="Z",
                start_month=3,
                start_year=2021,
                end_month=6,
                end_year=2022,
            ),
        ],
        answers={"phenom_": "skip", "other": "nope", "phenom_skill": "python"},
    )
    payload = build_application_payload(
        profile,
        job_id="1",
        custom_fields=custom_fields_from_answers(profile.answers),
    )
    assert len(payload["candidateData"]["experienceData"]) == 2
    assert payload["customFieldData"] == {"skill": "python"}


def test_hosted_profile_validation_failure() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")
    handler = _widgets_handler(detail)
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            job_title="Platform Engineer",
            company="Acme",
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config=_hosted_config(),
            profile=ProfileData(full_name="Ada", email=""),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "email" in result.error


def test_hosted_http_error_on_submit() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "search-results" in str(request.url):
            return httpx.Response(200, text=_SESSION_HTML)
        if str(request.url).endswith("/widgets"):
            return httpx.Response(200, json=detail)
        if str(request.url).endswith("/apply/v2/applications"):
            return httpx.Response(500, text="upstream boom")
        raise AssertionError(str(request.url))

    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=False,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config=_hosted_config(),
            credentials={"session": {"access_token": "tok"}},
        )
    )
    assert result.status == "failed"
    assert result.error is not None


def test_hosted_status_code_string_error() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")
    apply_posts: list[httpx.Request] = []
    handler = _widgets_handler(
        detail,
        apply_posts=apply_posts,
        apply_response=httpx.Response(
            200,
            json={"status": "ok", "statusCode": "400", "statusMessage": "rejected"},
        ),
    )
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=False,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config=_hosted_config(),
            credentials={"session": {"oauth_token": "tok"}},
        )
    )
    assert result.status == "failed"
    assert result.error == "rejected"


def test_discover_ref_num_when_config_omits_it() -> None:
    detail = load_json_fixture("phenom_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "search-results" in str(request.url):
            return httpx.Response(200, text=_SESSION_HTML)
        if request.method == "POST" and str(request.url).endswith("/widgets"):
            body = json.loads(request.content.decode())
            assert body.get("refNum") == "CISCISGLOBAL"
            return httpx.Response(200, json=detail)
        if "myworkdayjobs.com" in str(request.url):
            return httpx.Response(200, json={"jobPostingInfo": {}})
        raise AssertionError(str(request.url))

    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=True,
            config={
                "careers_base_url": "https://careers.cisco.com",
                "country": "global",
                "locale": "en_global",
            },
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["delegated_adapter"] == "workday"


def test_fetch_without_csrf_or_ref_num() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "search-results" in str(request.url):
            return httpx.Response(200, text="<html>no tokens</html>")
        if request.method == "POST" and str(request.url).endswith("/widgets"):
            assert request.headers.get("x-csrf-token") is None
            body = json.loads(request.content.decode())
            assert "refNum" not in body
            return httpx.Response(200, json=detail)
        raise AssertionError(str(request.url))

    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=True,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config={
                "careers_base_url": "https://careers.cisco.com",
                "country": "us",
                "locale": "en_us",
            },
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["phenom_route"] == "phenom_hosted"


def test_delegate_with_null_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.appliers.adapters import phenom as phenom_mod
    from app.appliers.types import ApplyResult

    class _Stub:
        def apply(self, ctx: ApplyContext) -> ApplyResult:
            return ApplyResult(status="dry_run", payload=None)

    monkeypatch.setattr(phenom_mod, "get_applier", lambda key, http=None: _Stub())
    applier = get_applier("phenom", http=make_http_client(lambda r: httpx.Response(500)))
    result = applier.apply(
        _ctx(
            dry_run=True,
            config={
                "apply_url": "https://boards.greenhouse.io/acme/jobs/99",
            },
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["delegated_payload"] is None
    assert result.payload["delegated_adapter"] == "greenhouse"


def test_hosted_submit_without_resume() -> None:
    detail = load_json_fixture("phenom_job_detail_hosted.json")
    apply_posts: list[httpx.Request] = []
    handler = _widgets_handler(detail, apply_posts=apply_posts)
    applier = get_applier("phenom", http=make_http_client(handler))
    result = applier.apply(
        _ctx(
            dry_run=False,
            with_resume=False,
            job_url="https://careers.cisco.com/us/en/job/ACMEGLOBALPHJOB1001EXTERNALENGLOBAL",
            config=_hosted_config(),
            credentials={"session": {"access_token": "tok"}},
        )
    )
    assert result.status == "submitted"
    assert "resumeData" not in result.payload["application"]  # type: ignore[index]


def test_hosted_error_helpers() -> None:
    from app.appliers.adapters.phenom_hosted import (
        _http_error_message,
        _response_json,
        _response_reports_error,
    )

    assert _response_reports_error({"status": "failed"}) is True
    assert _response_reports_error({"statusCode": 400}) is True
    assert _response_reports_error({"status": "success"}) is False
    assert _response_reports_error("x") is False

    class _Resp:
        def json(self) -> object:
            raise ValueError("bad json")

        @property
        def text(self) -> str:
            return " plain text "

    assert _response_json(_Resp()) == "plain text"  # type: ignore[arg-type]

    class _Empty:
        def json(self) -> object:
            raise ValueError("bad")

        @property
        def text(self) -> str:
            return "   "

    assert _response_json(_Empty()) is None  # type: ignore[arg-type]

    err = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://api.phenompro.com/apply/v2/applications"),
        response=httpx.Response(400, json={"message": "nope"}),
    )
    assert _http_error_message(err) == "nope"

    err2 = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://api.phenompro.com/apply/v2/applications"),
        response=httpx.Response(400, text="raw fail"),
    )
    assert "raw fail" in _http_error_message(err2)

    assert _http_error_message(httpx.ConnectError("offline")) == "offline"


def test_common_remaining_branches() -> None:
    from app.appliers.adapters.phenom_common import (
        extract_application_id,
        extract_error_message,
        resolve_access_token,
        resolve_careers_base_url,
        resolve_country,
        resolve_job_id,
        resolve_locale,
        resolve_ref_num,
    )

    assert resolve_careers_base_url({"careers_base_url": "https://x.com/"}, "") == "https://x.com"
    assert resolve_country({}, "https://careers.cisco.com/us/fr/job/x") == "us"
    assert resolve_country({}, "not-a-url") == "us"
    assert resolve_country({}, "https://careers.cisco.com/") == "us"
    assert resolve_locale({}, "https://careers.cisco.com/ca/fr/job/x") == "fr_ca"
    assert resolve_locale({}, "ftp://bad") == "en_us"
    assert resolve_locale({}, "https://careers.cisco.com/") == "en_us"
    assert resolve_ref_num({}, {"session": "bad"}) == ""
    assert resolve_job_id({}, "", "") is None
    assert resolve_job_id({}, "", "https://careers.cisco.com/us/en/jobs") is None
    assert resolve_job_id({}, "", "https://careers.cisco.com/us/en/job/") is None
    assert resolve_access_token({"session": "bad"}, {}) is None
    assert resolve_access_token({"session": {"access_token": "  "}}, {"api_token": "t"}) == "t"
    assert extract_error_message({"errors": []}) is None
    assert extract_error_message({"errors": "nope"}) is None
    assert extract_error_message({"errors": [123]}) is None
    assert extract_error_message({"errors": [{"errorMessage": "e1"}]}) == "e1"
    assert extract_error_message({"errors": [{}]}) is None
    assert extract_application_id({"id": 7}) == "7"
    assert extract_application_id({"data": {"candidateId": "c1"}}) == "c1"
    assert extract_application_id({"data": "x"}) is None
    assert extract_application_id({"data": {}}) is None


def test_payload_end_year_only_and_no_custom() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            WorkExperienceEntry(
                job_title="Eng",
                company="Y",
                start_month=1,
                start_year=2018,
                end_year=2019,
            ),
            WorkExperienceEntry(
                job_title="Lead",
                company="Z",
                start_month=2,
                start_year=2020,
                end_month=8,
                end_year=2021,
            ),
            WorkExperienceEntry(
                job_title="Open",
                company="NoEnd",
                start_month=5,
                start_year=2022,
            ),
            WorkExperienceEntry(job_title="Skip", company="NoDates"),
        ],
    )
    payload = build_application_payload(profile, job_id="1", custom_fields=None)
    assert "customFieldData" not in payload
    assert "experienceData" in payload["candidateData"]
    assert payload["candidateData"]["experienceData"][0]["fromTo"]["endDate"] == "2019"
    assert payload["candidateData"]["experienceData"][1]["fromTo"]["endDate"] == "08-2021"
    assert "endDate" not in payload["candidateData"]["experienceData"][2]["fromTo"]
    assert len(payload["candidateData"]["experienceData"]) == 3
    bare = ProfileData(full_name="Ada Lovelace", email="ada@example.com")
    bare_payload = build_application_payload(bare, job_id="1")
    assert "experienceData" not in bare_payload["candidateData"]
    assert "phoneNumber" not in bare_payload["candidateData"]["contactData"]


def test_same_host_false_when_base_missing() -> None:
    from app.appliers.adapters.phenom_route import _same_careers_host

    assert _same_careers_host("https://careers.cisco.com/apply", None) is False
    assert _same_careers_host("https://careers.cisco.com/apply", "https://other.com") is False


def test_http_error_empty_body() -> None:
    from app.appliers.adapters.phenom_hosted import _http_error_message

    err = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "https://api.phenompro.com/apply/v2/applications"),
        response=httpx.Response(502, content=b""),
    )
    assert _http_error_message(err) == "boom"
