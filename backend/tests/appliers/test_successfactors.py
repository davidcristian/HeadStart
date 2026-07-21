"""Tests for the SuccessFactors OData Recruiting apply adapter."""

from __future__ import annotations

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.successfactors import SuccessFactorsApplier
from app.appliers.adapters.successfactors_common import (
    basic_auth_header,
    extract_entity_id,
    extract_error_message,
    resolve_basic_auth,
    resolve_careers_base_url,
    resolve_company_id,
    resolve_country,
    resolve_job_id,
    resolve_locale,
    resolve_odata_base_url,
    talentcommunity_apply_url,
)
from app.appliers.adapters.successfactors_payload import (
    build_application_payload,
    build_attachment_payload,
    build_candidate_payload,
    build_dry_run_payload,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData, ProfileLinks, ResumeFile
from tests.conftest import load_json_fixture, make_http_client

_JOB_ID = "1746"
_COMPANY_ID = "WLGore"
_ODATA_BASE = "https://api4.successfactors.com"
_CAREERS = "https://wlgore.jobs.hr.cloud.sap"


def _profile(*, with_resume: bool = True) -> tuple[ProfileData, ResumeFile | None]:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(linkedin="linkedin.com/in/ada"),
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"sf_customField": "open source", "country": "United Kingdom"},
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


def _handler(
    *,
    fail_candidate: bool = False,
    fail_attachment: bool = False,
    fail_application: bool = False,
    missing_candidate_id: bool = False,
    missing_attachment_id: bool = False,
    application_error_body: bool = False,
) -> dict[str, object]:
    candidate = load_json_fixture("successfactors_candidate_created.json")
    attachment = load_json_fixture("successfactors_attachment_created.json")
    application = load_json_fixture("successfactors_application_created.json")
    error = load_json_fixture("successfactors_odata_error.json")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/odata/v2/Candidate") and request.method == "POST":
            if fail_candidate:
                return httpx.Response(400, json=error)
            assert request.headers.get("Authorization", "").startswith("Basic ")
            if missing_candidate_id:
                return httpx.Response(201, json={"d": {"firstName": "Ada"}})
            return httpx.Response(201, json=candidate)
        if path.endswith("/odata/v2/Attachment") and request.method == "POST":
            if fail_attachment:
                return httpx.Response(400, json=error)
            if missing_attachment_id:
                return httpx.Response(201, json={"d": {"fileName": "ada.pdf"}})
            return httpx.Response(201, json=attachment)
        if path.endswith("/odata/v2/JobApplication") and request.method == "POST":
            if fail_application:
                return httpx.Response(400, json=error)
            if application_error_body:
                return httpx.Response(200, json=error)
            return httpx.Response(201, json=application)
        return httpx.Response(404, text=f"not found: {request.method} {path}")

    return {"handler": handler, "calls": calls}


def _ctx(
    *,
    dry_run: bool = True,
    with_resume: bool = True,
    job_external_id: str = _JOB_ID,
    job_url: str = (f"{_CAREERS}/job/Internship-Title/{_JOB_ID}-en_US/"),
    config: dict | None = None,
    credentials: dict | None = None,
    include_odata: bool = True,
) -> ApplyContext:
    profile, resume = _profile(with_resume=with_resume)
    cfg: dict = {
        "careers_base_url": _CAREERS,
        "locale": "en_US",
        **(config or {}),
    }
    if include_odata:
        cfg.setdefault("odata_base_url", _ODATA_BASE)
        cfg.setdefault("company_id", _COMPANY_ID)
    creds = credentials
    if creds is None and not dry_run:
        creds = {"session": {"username": "apiuser", "password": "secret"}}
    return ApplyContext(
        job_external_id=job_external_id,
        job_title="Internship Marketing",
        company="W. L. Gore",
        job_url=job_url,
        config=cfg,
        profile=profile,
        resume_file=resume,
        credentials=creds,
        dry_run=dry_run,
    )


def test_has_applier_registers_successfactors() -> None:
    assert has_applier("successfactors")
    assert get_applier("successfactors").__class__.__name__ == "SuccessFactorsApplier"


def test_resolve_job_id_from_url_and_config() -> None:
    assert resolve_job_id({}, "", f"{_CAREERS}/job/Slug-Title/{_JOB_ID}-en_US/") == _JOB_ID
    assert resolve_job_id({}, "", f"{_CAREERS}/talentcommunity/apply/{_JOB_ID}/") == _JOB_ID
    assert resolve_job_id({"job_req_id": "999"}, "1", "") == "999"
    assert resolve_job_id({}, "abc", "") is None


def test_resolve_careers_locale_country_odata() -> None:
    assert resolve_careers_base_url({}, f"{_CAREERS}/job/x/1-en_US/") == _CAREERS
    assert resolve_careers_base_url({}, "https://example.com/job/1") is None
    assert resolve_locale({}) == "en_US"
    assert resolve_locale({"locale": "de_DE"}) == "de_DE"
    assert resolve_country({}, {"country": "Germany"}) == "Germany"
    assert resolve_country({}, {}) == "United States"
    assert resolve_odata_base_url({"odata_base_url": _ODATA_BASE}, None) == _ODATA_BASE
    assert resolve_odata_base_url({"api_base_url": "https://evil.example"}, None) is None
    assert resolve_odata_base_url({}, {"session": {"sf_api_base_url": _ODATA_BASE}}) == _ODATA_BASE
    assert resolve_company_id({"company_id": _COMPANY_ID}, None) == _COMPANY_ID
    assert talentcommunity_apply_url(_CAREERS, _JOB_ID, "en_US").endswith(
        f"/talentcommunity/apply/{_JOB_ID}/?locale=en_US"
    )


def test_resolve_basic_auth_appends_company_id() -> None:
    auth = resolve_basic_auth(
        {"session": {"username": "apiuser", "password": "secret"}},
        {},
        company_id=_COMPANY_ID,
    )
    assert auth == (f"apiuser@{_COMPANY_ID}", "secret")
    assert basic_auth_header(*auth).startswith("Basic ")
    assert (
        resolve_basic_auth(
            {"session": {"username": f"apiuser@{_COMPANY_ID}", "password": "x"}},
            {},
            company_id=_COMPANY_ID,
        )[0]
        == f"apiuser@{_COMPANY_ID}"
    )
    assert resolve_basic_auth(None, {}, company_id=_COMPANY_ID) is None


def test_payload_builders() -> None:
    profile, resume = _profile()
    candidate = build_candidate_payload(profile, country="United Kingdom")
    assert candidate["primaryEmail"] == "ada@example.com"
    assert candidate["country"] == "United Kingdom"
    assert candidate["agreeToPrivacyStatement"] == "true"

    application = build_application_payload(
        profile,
        job_req_id=_JOB_ID,
        candidate_id="9001",
        cover_letter="Hello",
        attachment_id="7001",
        config={"sf_field_source": "HeadStart"},
    )
    assert application["jobReqId"] == 1746
    assert application["candidateId"] == "9001"
    assert application["customField"] == "open source"
    assert application["source"] == "HeadStart"
    assert application["resume"]["__metadata"]["uri"] == "Attachment(7001)"

    attachment = build_attachment_payload(resume)  # type: ignore[arg-type]
    assert attachment["fileName"] == "ada.pdf"
    assert "fileContent" in attachment

    preview = build_dry_run_payload(
        candidate=candidate,
        application=application,
        job_id=_JOB_ID,
        careers_base_url=_CAREERS,
        apply_url=talentcommunity_apply_url(_CAREERS, _JOB_ID, "en_US"),
        odata_base_url=None,
        company_id=None,
        locale="en_US",
        resume_file=resume,
        attachment=attachment,
    )
    assert preview["successfactors_route"] == "portal_blocked"
    assert preview["blocker"]
    assert preview["attachment"]["fileContent"] == "<omitted>"


def test_payload_validation_errors() -> None:
    bare = ProfileData(full_name="Ada", email="", phone="", location="")
    try:
        build_candidate_payload(bare, country="US")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "last name" in str(exc) or "email" in str(exc)

    named = ProfileData(full_name="Ada Lovelace", email="", phone="", location="")
    try:
        build_candidate_payload(named, country="US")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "email" in str(exc)

    try:
        build_candidate_payload(
            ProfileData(full_name="Ada Lovelace", email="a@b.c", phone="", location=""),
            country="  ",
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "country" in str(exc)


def test_extract_helpers() -> None:
    created = load_json_fixture("successfactors_candidate_created.json")
    assert extract_entity_id(created, "candidateId") == "9001"
    err = load_json_fixture("successfactors_odata_error.json")
    assert "jobReqId is invalid" in extract_error_message(err)
    assert extract_error_message("plain") == "plain"
    assert extract_error_message({}) == "successfactors apply failed"


def test_dry_run_preview() -> None:
    bundle = _handler()
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=True))
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["job_req_id"] == _JOB_ID
    assert result.payload["candidate"]["firstName"] == "Ada"
    assert "Dear W. L. Gore" in result.payload["application"]["coverLetter"]
    assert result.payload["attachment"]["fileContent"] == "<omitted>"
    assert bundle["calls"] == []


def test_dry_run_without_odata_shows_blocker() -> None:
    applier = SuccessFactorsApplier(http=make_http_client(lambda _: httpx.Response(200)))
    result = applier.apply(_ctx(dry_run=True, include_odata=False))
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["successfactors_route"] == "portal_blocked"
    assert result.payload["blocker"]


def test_live_submit_candidate_attachment_application() -> None:
    bundle = _handler()
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False))
    assert result.status == "submitted"
    assert result.external_application_id == "8001"
    assert result.payload is not None
    assert result.payload["candidate_id"] == "9001"
    assert result.payload["attachment_id"] == "7001"
    paths = [c.url.path for c in bundle["calls"]]  # type: ignore[index]
    assert paths == [
        "/odata/v2/Candidate",
        "/odata/v2/Attachment",
        "/odata/v2/JobApplication",
    ]
    app_body = json.loads(bundle["calls"][2].content.decode())  # type: ignore[index]
    assert app_body["candidateId"] == "9001"
    assert app_body["resume"]["__metadata"]["uri"] == "Attachment(7001)"


def test_live_submit_without_resume_skips_attachment() -> None:
    bundle = _handler()
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False, with_resume=False))
    assert result.status == "submitted"
    paths = [c.url.path for c in bundle["calls"]]  # type: ignore[index]
    assert paths == ["/odata/v2/Candidate", "/odata/v2/JobApplication"]


def test_live_missing_odata_config_fails() -> None:
    applier = SuccessFactorsApplier(http=make_http_client(lambda _: httpx.Response(200)))
    result = applier.apply(_ctx(dry_run=False, include_odata=False))
    assert result.status == "failed"
    assert result.error is not None
    assert "odata_base_url" in result.error


def test_live_missing_auth_fails() -> None:
    applier = SuccessFactorsApplier(http=make_http_client(lambda _: httpx.Response(200)))
    result = applier.apply(_ctx(dry_run=False, credentials={}))
    assert result.status == "failed"
    assert result.error is not None
    assert "Basic Auth" in result.error


def test_live_candidate_http_error() -> None:
    bundle = _handler(fail_candidate=True)
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False))
    assert result.status == "failed"
    assert result.error is not None
    assert "jobReqId is invalid" in result.error


def test_live_missing_candidate_id() -> None:
    bundle = _handler(missing_candidate_id=True)
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False, with_resume=False))
    assert result.status == "failed"
    assert result.error is not None
    assert "candidateId" in result.error


def test_live_attachment_http_error() -> None:
    bundle = _handler(fail_attachment=True)
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False))
    assert result.status == "failed"
    assert result.error is not None


def test_live_missing_attachment_id() -> None:
    bundle = _handler(missing_attachment_id=True)
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False))
    assert result.status == "failed"
    assert result.error is not None
    assert "attachmentId" in result.error


def test_live_application_http_error() -> None:
    bundle = _handler(fail_application=True)
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False, with_resume=False))
    assert result.status == "failed"
    assert result.error is not None


def test_live_application_error_envelope() -> None:
    bundle = _handler(application_error_body=True)
    applier = SuccessFactorsApplier(http=make_http_client(bundle["handler"]))
    result = applier.apply(_ctx(dry_run=False, with_resume=False))
    assert result.status == "failed"
    assert result.error is not None
    assert "jobReqId is invalid" in result.error


def test_missing_job_id_fails() -> None:
    applier = SuccessFactorsApplier(http=make_http_client(lambda _: httpx.Response(200)))
    result = applier.apply(_ctx(dry_run=True, job_external_id="", job_url="https://example.com/"))
    assert result.status == "failed"
    assert result.error is not None
    assert "job id" in result.error


def test_invalid_profile_fails_before_network() -> None:
    applier = SuccessFactorsApplier(http=make_http_client(lambda _: httpx.Response(200)))
    ctx = _ctx(dry_run=True)
    ctx.profile.full_name = "Ada"
    ctx.profile.email = ""
    result = applier.apply(ctx)
    assert result.status == "failed"


def test_cover_letter_override_and_privacy_false() -> None:
    applier = SuccessFactorsApplier(http=make_http_client(lambda _: httpx.Response(200)))
    ctx = _ctx(dry_run=True, with_resume=False, config={"agree_to_privacy_statement": False})
    ctx.cover_letter = "Custom cover"
    ctx.profile.phone = ""
    result = applier.apply(ctx)
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["candidate"]["agreeToPrivacyStatement"] == "false"
    assert "cellPhone" not in result.payload["candidate"]
    assert result.payload["application"]["coverLetter"] == "Custom cover"


def test_resolve_job_id_trailing_segment_and_apply_only() -> None:
    assert resolve_job_id({}, "", f"{_CAREERS}/openings/1746") == "1746"
    assert resolve_job_id({}, "", f"{_CAREERS}/talentcommunity/apply/not-a-id/") is None
    assert resolve_job_id({}, "", "not-a-url") is None


def test_resolve_careers_edge_cases() -> None:
    assert resolve_careers_base_url({"careers_base_url": _CAREERS}, "") == _CAREERS
    assert resolve_careers_base_url({}, "") is None
    assert resolve_careers_base_url({}, "ftp://wlgore.jobs.hr.cloud.sap/job/1") is None
    assert resolve_careers_base_url({}, "https://jobs.hr.cloud.sap/") == "https://jobs.hr.cloud.sap"
    assert resolve_locale({"locale": "   "}) == "en_US"
    assert resolve_country({"sf_country": "Canada"}, {}) == "Canada"
    assert resolve_country({"candidate_country": "France"}, {}) == "France"


def test_resolve_auth_from_config_and_odata_proxy() -> None:
    assert resolve_company_id({}, {"session": {"sf_company_id": "ACME"}}) == "ACME"
    assert resolve_company_id({}, {"session": {"tenant_id": "T1"}}) == "T1"
    auth = resolve_basic_auth(
        None,
        {"api_username": "cfguser", "api_password": "cfgpass"},
        company_id="ACME",
    )
    assert auth == ("cfguser@ACME", "cfgpass")
    assert (
        resolve_odata_base_url({"odata_base_url": "https://proxy.example/odata/v2"}, None)
        == "https://proxy.example/odata/v2"
    )
    assert resolve_odata_base_url({"odata_base_url": "ftp://api4.successfactors.com"}, None) is None


def test_extract_entity_and_error_variants() -> None:
    from app.appliers.adapters.successfactors_common import (
        http_error_message,
        odata_reports_error,
        response_json,
    )

    assert extract_entity_id("nope", "id") is None
    assert extract_entity_id({"d": ["x"]}, "id") is None
    assert extract_entity_id({"d": {"id": 7}}, "id") == "7"
    assert extract_entity_id({"id": "  "}, "id") is None
    assert extract_error_message({"error": {"message": "top"}}) == "top"
    assert extract_error_message({"error": {"message": {"value": "  "}}, "detail": "fallback"}) == (
        "fallback"
    )
    assert extract_error_message({"error": {"message": None}, "errorMessage": "em2"}) == "em2"
    assert extract_error_message({"message": "m"}) == "m"
    assert extract_error_message({"errorMessage": "em"}) == "em"
    assert odata_reports_error({"error": {}}) is True
    assert odata_reports_error({}) is False

    class _Resp:
        text = "plain-body"

        def json(self) -> object:
            raise ValueError("no json")

    assert response_json(_Resp()) == "plain-body"  # type: ignore[arg-type]

    class _Empty:
        text = ""

        def json(self) -> object:
            raise ValueError("no json")

    assert response_json(_Empty()) == {}  # type: ignore[arg-type]
    assert http_error_message(httpx.ConnectError("boom")) == "boom"

    request = httpx.Request("POST", "https://api4.successfactors.com/odata/v2/Candidate")
    response = httpx.Response(400, request=request, text="not-json")
    assert http_error_message(httpx.HTTPStatusError("bad", request=request, response=response)) in {
        "bad",
        "not-json",
    }

    response_json_ok = httpx.Response(
        400,
        request=request,
        json={"error": {"message": {"value": "from-body"}}},
    )
    assert (
        http_error_message(httpx.HTTPStatusError("x", request=request, response=response_json_ok))
        == "from-body"
    )


def test_application_payload_validation_and_skips() -> None:
    bare = ProfileData(full_name="Ada", email="a@b.c", phone="", location="")
    try:
        build_application_payload(bare, job_req_id="1", candidate_id=None)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "last name" in str(exc)

    no_email = ProfileData(full_name="Ada Lovelace", email="", phone="", location="")
    try:
        build_application_payload(no_email, job_req_id="1", candidate_id=None)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "email" in str(exc)

    profile, _ = _profile(with_resume=False)
    profile.answers = {"sf_": "skip", "other": "x", "sf_ok": "y"}
    app = build_application_payload(
        profile,
        job_req_id="abc",
        candidate_id=None,
        cover_letter=None,
        config={"sf_field_": "skip", "sf_field_ok2": "z", "other": 1},
    )
    assert app["jobReqId"] == "abc"
    assert app["ok"] == "y"
    assert app["ok2"] == "z"
    assert "candidateId" not in app
