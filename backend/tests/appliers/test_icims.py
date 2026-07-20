"""Tests for the iCIMS Talent Cloud Partner API apply adapter."""

from __future__ import annotations

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.icims import IcimsApplier
from app.appliers.adapters.icims_common import (
    basic_auth_header,
    customer_id_from_job_detail,
    extract_error_message,
    parse_created_id,
    resolve_basic_auth,
    resolve_careers_base_url,
    resolve_customer_id,
    resolve_job_id,
)
from app.appliers.adapters.icims_payload import (
    build_dry_run_payload,
    build_person_payload,
    build_workflow_payload,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData, ProfileLinks, ResumeFile
from tests.conftest import load_json_fixture, make_http_client

_JOB_ID = "31370"
_CUSTOMER_ID = "13315"


def _profile(*, with_resume: bool = True) -> tuple[ProfileData, ResumeFile | None]:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(linkedin="linkedin.com/in/ada"),
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"icims_field9999": "open source", "address_city": "London"},
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


def _handler(*, fail_people: bool = False, fail_workflow: bool = False) -> dict[str, object]:
    detail = load_json_fixture("icims_job_detail.json")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if host == "careers.rivian.com" and path.endswith("/api/jobs"):
            return httpx.Response(200, json=detail)
        if path.endswith(f"/customers/{_CUSTOMER_ID}/people") and request.method == "POST":
            if fail_people:
                return httpx.Response(
                    401,
                    json={
                        "errors": [
                            {
                                "errorMessage": "You must provide authentication details",
                                "errorCode": 6,
                            }
                        ]
                    },
                )
            assert request.headers.get("Authorization", "").startswith("Basic ")
            return httpx.Response(
                201,
                headers={"Location": f"https://api.icims.com/customers/{_CUSTOMER_ID}/people/42"},
            )
        if (
            path.endswith(f"/customers/{_CUSTOMER_ID}/applicantworkflows")
            and request.method == "POST"
        ):
            if fail_workflow:
                return httpx.Response(
                    400,
                    json={"errors": [{"errorMessage": "Invalid job id", "errorCode": 2}]},
                )
            body = json.loads(request.content.decode())
            assert body["associatedprofile"] == 42
            assert body["baseprofile"] == int(_JOB_ID)
            return httpx.Response(
                201,
                headers={
                    "Location": (
                        f"https://api.icims.com/customers/{_CUSTOMER_ID}/applicantworkflows/99"
                    )
                },
            )
        return httpx.Response(404, text=f"not found: {request.method} {host}{path}")

    return {"handler": handler, "calls": calls, "detail": detail}


def test_has_applier_registers_icims() -> None:
    assert has_applier("icims")
    assert get_applier("icims").__class__.__name__ == "IcimsApplier"


def test_resolve_helpers() -> None:
    assert resolve_careers_base_url({"careers_base_url": "https://careers.rivian.com/"}, "") == (
        "https://careers.rivian.com"
    )
    assert (
        resolve_careers_base_url({}, "https://careers.rivian.com/jobs/31370")
        == "https://careers.rivian.com"
    )
    assert (
        resolve_careers_base_url({}, "https://us-careers-rivian.icims.com/jobs/31370/login") is None
    )
    assert resolve_job_id({}, _JOB_ID, "") == _JOB_ID
    assert resolve_job_id({}, "", "https://careers.rivian.com/jobs/31370") == _JOB_ID
    assert resolve_job_id({}, "not-numeric", "") is None
    assert resolve_customer_id({"customer_id": _CUSTOMER_ID}, None) == _CUSTOMER_ID
    assert resolve_customer_id({}, {"session": {"tenant_id": _CUSTOMER_ID}}) == _CUSTOMER_ID
    detail = load_json_fixture("icims_job_detail.json")
    assert isinstance(detail, dict)
    job = detail["jobs"][0]["data"]
    assert customer_id_from_job_detail(job) == _CUSTOMER_ID
    assert resolve_basic_auth({"session": {"username": "u", "password": "p"}}, {}) == ("u", "p")
    assert resolve_basic_auth(None, {"api_username": "u", "api_password": "p"}) == ("u", "p")
    assert resolve_basic_auth(None, {}) is None
    assert parse_created_id("https://api.icims.com/customers/13315/people/42/") == "42"
    assert parse_created_id(None) is None
    assert basic_auth_header("u", "p").startswith("Basic ")


def test_payload_helpers_map_profile() -> None:
    profile, resume = _profile()
    person = build_person_payload(
        profile,
        config={"folder_id": "D32007", "address_country_id": "D41001"},
        cover_letter="Hello Rivian",
        resume_file=resume,
    )
    assert person["firstname"] == "Ada"
    assert person["lastname"] == "Lovelace"
    assert person["email"] == "ada@example.com"
    assert person["folder"]["id"] == "D32007"
    assert person["phones"][0]["phonenumber"] == "+1 555 0100"
    assert person["addresses"][0]["addresscity"] == "London"
    assert person["overview"] == "Hello Rivian"
    assert person["field9999"] == "open source"
    assert person["resume"]["filename"] == "ada.pdf"
    workflow = build_workflow_payload(job_id=_JOB_ID, person_id="42", config={})
    assert workflow["baseprofile"] == 31370
    assert workflow["associatedprofile"] == 42
    preview = build_dry_run_payload(
        person=person,
        workflow=workflow,
        customer_id=_CUSTOMER_ID,
        job_id=_JOB_ID,
        careers_base_url="https://careers.rivian.com",
        apply_url="https://us-careers-rivian.icims.com/jobs/31370/login",
        job_detail={
            "slug": _JOB_ID,
            "title": "Engineer",
            "hiring_organization": "Rivian",
            "apply_url": "https://us-careers-rivian.icims.com/jobs/31370/login",
            "full_location": "Normal, Illinois",
        },
    )
    assert preview["customer_id"] == _CUSTOMER_ID
    assert preview["job"]["title"] == "Engineer"
    assert "people" in preview["live_submit"]


def test_payload_requires_name_and_email() -> None:
    bare = ProfileData(full_name="Ada", email="", phone="", location="")
    try:
        build_person_payload(bare, config={})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "first and last" in str(exc)
    bare2 = ProfileData(full_name="Ada Lovelace", email="  ", phone="", location="")
    try:
        build_person_payload(bare2, config={})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "email" in str(exc)


def test_extract_error_message_variants() -> None:
    assert extract_error_message({"errors": [{"errorMessage": "boom"}]}) == "boom"
    assert extract_error_message({"errors": ["nope"]}) == "nope"
    assert extract_error_message({"message": "msg"}) == "msg"
    assert extract_error_message("plain") == "plain"
    assert extract_error_message({}) == "icims apply failed"


def test_dry_run_previews_partner_payload() -> None:
    profile, resume = _profile()
    fixture = _handler()
    http = make_http_client(fixture["handler"])  # type: ignore[arg-type]
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url=f"https://careers.rivian.com/jobs/{_JOB_ID}",
            config={"careers_base_url": "https://careers.rivian.com"},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["customer_id"] == _CUSTOMER_ID
    assert result.payload["person"]["firstname"] == "Ada"
    assert result.payload["applicantworkflow"]["baseprofile"] == 31370
    assert result.payload["apply_url"].endswith("/login")
    assert any(c.url.path.endswith("/api/jobs") for c in fixture["calls"])  # type: ignore[index]


def test_dry_run_without_careers_base_still_works() -> None:
    profile, resume = _profile()
    http = make_http_client(lambda request: httpx.Response(500, text="no"))
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={"customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["customer_id"] == _CUSTOMER_ID


def test_live_submit_creates_person_and_workflow() -> None:
    profile, resume = _profile()
    fixture = _handler()
    http = make_http_client(fixture["handler"])  # type: ignore[arg-type]
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url=f"https://careers.rivian.com/jobs/{_JOB_ID}",
            config={"careers_base_url": "https://careers.rivian.com"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"username": "partner", "password": "secret"}},
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "99"
    assert result.payload is not None
    assert result.payload["person_id"] == "42"
    assert result.payload["workflow_id"] == "99"


def test_live_submit_requires_customer_id_and_auth() -> None:
    profile, resume = _profile()
    http = make_http_client(lambda request: httpx.Response(404, text="no"))
    missing_customer = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={},
            profile=profile,
            resume_file=resume,
            dry_run=False,
        )
    )
    assert missing_customer.status == "failed"
    assert missing_customer.error is not None
    assert "customer_id" in missing_customer.error

    missing_auth = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={"customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            dry_run=False,
        )
    )
    assert missing_auth.status == "failed"
    assert missing_auth.error is not None
    assert "Basic Auth" in missing_auth.error


def test_live_submit_maps_http_errors() -> None:
    profile, resume = _profile()
    people_fail = _handler(fail_people=True)
    http = make_http_client(people_fail["handler"])  # type: ignore[arg-type]
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={"customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"username": "partner", "password": "secret"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "authentication" in result.error.lower()

    workflow_fail = _handler(fail_workflow=True)
    http2 = make_http_client(workflow_fail["handler"])  # type: ignore[arg-type]
    result2 = IcimsApplier(http=http2).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={"customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"username": "partner", "password": "secret"}},
            dry_run=False,
        )
    )
    assert result2.status == "failed"
    assert result2.error == "Invalid job id"


def test_missing_job_id_fails() -> None:
    profile, resume = _profile()
    http = make_http_client(lambda request: httpx.Response(404, text="no"))
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id="",
            job_title="Engineer",
            company="Rivian",
            job_url="https://example.com/careers",
            config={},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "job id" in result.error


def test_live_submit_missing_location_header() -> None:
    profile, resume = _profile()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/people"):
            return httpx.Response(201, headers={})
        return httpx.Response(404, text="no")

    http = make_http_client(handler)
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={"customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"username": "partner", "password": "secret"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "Location" in result.error


def test_job_detail_fetch_tolerates_bad_payloads() -> None:
    profile, resume = _profile()

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/jobs" in request.url.path:
            return httpx.Response(200, json={"jobs": "nope"})
        return httpx.Response(404, text="no")

    http = make_http_client(handler)
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url=f"https://careers.rivian.com/jobs/{_JOB_ID}",
            config={"careers_base_url": "https://careers.rivian.com", "customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["customer_id"] == _CUSTOMER_ID


def test_http_error_without_json_body() -> None:
    profile, resume = _profile()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    http = make_http_client(handler)
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={"customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"username": "partner", "password": "secret"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None


def test_customer_id_from_job_detail_fallbacks() -> None:
    assert customer_id_from_job_detail({}) is None
    assert customer_id_from_job_detail({"meta_data": "x"}) is None
    assert customer_id_from_job_detail({"meta_data": {"icims": "x"}}) is None
    assert customer_id_from_job_detail({"meta_data": {"icims": {"tenantId": "99"}}}) == "99"
    assert (
        customer_id_from_job_detail(
            {"meta_data": {"icims": {"primary_posted_site_object": {"tenant_id": "88"}}}}
        )
        == "88"
    )


def test_invalid_profile_fails_before_network() -> None:
    bare = ProfileData(full_name="Ada", email="ada@example.com", phone="", location="")
    http = make_http_client(lambda request: httpx.Response(500, text="no"))
    result = IcimsApplier(http=http).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url="",
            config={"customer_id": _CUSTOMER_ID},
            profile=bare,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "full_name" in result.error


def test_payload_optional_branches_and_notes_fallbacks() -> None:
    minimal = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="",
        location="",
        cover_letter_template="",
        answers={"icims_": "skip", "icims_field1": "", "notes": "from answers"},
    )
    person = build_person_payload(minimal, config={"notes_field": "   "})
    assert "phones" not in person
    assert "addresses" not in person
    assert person["overview"] == "from answers"

    with_location = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="City",
        cover_letter_template="Template body",
        answers={},
    )
    person2 = build_person_payload(
        with_location,
        config={
            "phone_type_id": "   ",
            "address_type_id": "   ",
            "address_state_id": "D41001046",
        },
    )
    assert person2["overview"] == "Template body"
    assert person2["phones"][0]["phonetype"]["id"] == "D83002"
    assert person2["addresses"][0]["addresstype"]["id"] == "D84002"
    assert person2["addresses"][0]["addressstate"]["id"] == "D41001046"

    workflow = build_workflow_payload(job_id="ABC", person_id="XYZ", config={"status_id": "  "})
    assert workflow["baseprofile"] == "ABC"
    assert workflow["associatedprofile"] == "XYZ"
    assert workflow["status"]["id"] == "D10100"

    preview = build_dry_run_payload(
        person=person,
        workflow=workflow,
        customer_id=None,
        job_id=_JOB_ID,
        careers_base_url=None,
        apply_url=None,
        job_detail={"req_id": _JOB_ID, "short_location": "Remote"},
    )
    assert "<customer_id>" in preview["live_submit"]["people"]
    assert preview["job"]["full_location"] == "Remote"


def test_resolve_edge_cases() -> None:
    assert resolve_careers_base_url({}, "") is None
    assert resolve_careers_base_url({}, "not-a-url") is None
    assert resolve_job_id({}, "", "https://careers.rivian.com/openings") is None
    assert resolve_job_id({}, "", "https://careers.rivian.com/jobs/") is None
    assert resolve_customer_id({}, None, None) is None
    assert (
        customer_id_from_job_detail(
            {"meta_data": {"icims": {"primary_posted_site_object": {"tenantId": "nope"}}}}
        )
        is None
    )
    assert (
        customer_id_from_job_detail(
            {"meta_data": {"icims": {"primary_posted_site_object": {}, "customerId": "77"}}}
        )
        == "77"
    )
    assert extract_error_message({"errors": [{"message": "alt"}]}) == "alt"
    assert extract_error_message({"error": "e"}) == "e"
    assert extract_error_message({"detail": "d"}) == "d"
    assert extract_error_message({"errors": [{"errorMessage": ""}], "message": "fallback"}) == (
        "fallback"
    )
    assert extract_error_message({"errors": ["  "], "errorMessage": "top"}) == "top"
    assert extract_error_message({"errors": [123], "detail": "num"}) == "num"


def test_fetch_job_detail_variants() -> None:
    profile, resume = _profile(with_resume=False)
    profile.cover_letter_template = ""

    payloads = iter(
        [
            httpx.Response(500, text="err"),
            httpx.Response(200, json=["nope"]),
            httpx.Response(
                200,
                json={
                    "jobs": [
                        "skip",
                        {"data": "bad"},
                        {"data": {"slug": "99999", "title": "Other"}},
                        {"slug": _JOB_ID, "title": "Match", "apply_url": 123},
                    ]
                },
            ),
            httpx.Response(
                200,
                json={"jobs": [{"data": {"slug": "00000", "title": "No match"}}]},
            ),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(payloads)

    http = make_http_client(handler)
    applier = IcimsApplier(http=http)

    # HTTP error → None customer from fetch
    r1 = applier.apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url=f"https://careers.rivian.com/jobs/{_JOB_ID}",
            config={"careers_base_url": "https://careers.rivian.com", "customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert r1.status == "dry_run"

    r2 = applier.apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url=f"https://careers.rivian.com/jobs/{_JOB_ID}",
            config={"careers_base_url": "https://careers.rivian.com", "customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert r2.status == "dry_run"

    r3 = applier.apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url=f"https://careers.rivian.com/jobs/{_JOB_ID}",
            config={"careers_base_url": "https://careers.rivian.com", "customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            dry_run=True,
            cover_letter="  explicit  ",
        )
    )
    assert r3.status == "dry_run"
    assert r3.payload is not None
    assert r3.payload["person"]["overview"] == "explicit"
    assert r3.payload["apply_url"] is None

    r4 = applier.apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Engineer",
            company="Rivian",
            job_url=f"https://careers.rivian.com/jobs/{_JOB_ID}",
            config={"careers_base_url": "https://careers.rivian.com", "customer_id": _CUSTOMER_ID},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert r4.status == "dry_run"
    assert r4.payload is not None
    assert r4.payload["job"] is None


def test_http_error_message_without_response() -> None:
    from app.appliers.adapters import icims as icims_mod

    assert "connect" in icims_mod._http_error_message(httpx.ConnectError("connect")).lower() or (
        "connect" in str(httpx.ConnectError("connect")).lower()
    )
    request = httpx.Request("POST", "https://api.icims.com/customers/1/people")
    response = httpx.Response(500, request=request, text="{not-json")
    err = httpx.HTTPStatusError("bad", request=request, response=response)
    assert icims_mod._http_error_message(err)
