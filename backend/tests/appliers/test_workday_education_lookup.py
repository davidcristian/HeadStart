"""Tests for Workday education lookup resolution."""

import httpx

from app.appliers.adapters.workday_education_lookup import (
    EducationLookupResolver,
    build_education_lookup_resolver,
)
from app.appliers.adapters.workday_experience import build_education_body, preview_educations
from app.schemas.profile import EducationEntry, ProfileData
from tests.appliers.workday_helpers import JOB_URL, WORKDAY_CREDENTIALS
from tests.conftest import load_json_fixture, make_http_client


def test_build_education_body_uses_resolved_degree_and_field_ids() -> None:
    body = build_education_body(
        EducationEntry(
            school="Example University",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
        ),
        degree={"id": "degree-wid"},
        field_of_study={"id": "field-wid"},
    )
    assert body["degree"] == {"id": "degree-wid"}
    assert body["fieldOfStudy"] == {"id": "field-wid"}


def test_resolver_maps_degree_and_field_to_catalog_ids() -> None:
    degree_fixture = load_json_fixture("workday_institutionvalues_degree.json")
    field_fixture = load_json_fixture("workday_institutionvalues_field_of_study.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/degree"):
            return httpx.Response(200, json=degree_fixture)
        if request.url.path.endswith("/institutionvalues/fieldOfStudy"):
            return httpx.Response(200, json=field_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    target = _target()
    resolver = EducationLookupResolver(
        make_http_client(handler),
        target=target,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    degree, field = resolver.references_for(
        EducationEntry(
            school="Example University",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
        )
    )
    assert degree == {"id": "a1b2c3d4e5f6478990a1b2c3d4e5f678"}
    assert field == {"id": "d4e5f6478990a1b2c3d4e5f678012345"}


def test_preview_educations_uses_lookup_when_resolver_available() -> None:
    degree_fixture = load_json_fixture("workday_institutionvalues_degree.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/degree"):
            return httpx.Response(200, json=degree_fixture)
        if request.url.path.endswith("/institutionvalues/fieldOfStudy"):
            return httpx.Response(200, json={"total": 0, "data": []})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    target = _target()
    resolver = build_education_lookup_resolver(
        make_http_client(handler),
        target=target,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    previews = preview_educations(
        ProfileData(
            education=[
                EducationEntry(
                    school="Example University",
                    degree="BS",
                    field_of_study="Unknown Field",
                )
            ]
        ),
        resolver=resolver,
    )
    assert previews[0]["degree"] == {"id": "b2c3d4e5f6478990a1b2c3d4e5f67801"}
    assert previews[0]["fieldOfStudy"] == {"descriptor": "Unknown Field"}


def test_resolver_honors_config_aliases_without_network() -> None:
    resolver = EducationLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={
            "education_lookup_aliases": {
                "degree:Bachelor of Science": "a1b2c3d4e5f6478990a1b2c3d4e5f678"
            }
        },
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.degree_reference("Bachelor of Science") == {
        "id": "a1b2c3d4e5f6478990a1b2c3d4e5f678"
    }


def test_resolver_skips_lookup_when_disabled() -> None:
    resolver = EducationLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={"skip_education_lookup": True},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.degree_reference("Bachelor of Science") == {"descriptor": "Bachelor of Science"}


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")


def _target():
    from app.appliers.adapters.workday_common import resolve_target

    target = resolve_target(
        {"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
        JOB_URL,
    )
    assert target is not None
    return target
