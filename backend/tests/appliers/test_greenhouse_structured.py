"""Tests for Greenhouse structured profile mapping."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.greenhouse import build_application_payload
from app.appliers.adapters.greenhouse_structured import (
    GreenhouseEducationResolver,
    _config_default_id,
    _parse_greenhouse_items,
    build_education,
    build_education_lookup_resolver,
    build_employment,
    build_employments,
)
from app.appliers.base import get_applier
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry
from tests.conftest import load_json_fixture, make_http_client


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")


def test_build_employment_maps_current_role_and_end_date() -> None:
    body = build_employment(
        WorkExperienceEntry(
            job_title="Engineer",
            company="ACME",
            start_month=3,
            start_year=2020,
            end_month=6,
            end_year=2023,
        )
    )
    assert body == {
        "company_name": "ACME",
        "title": "Engineer",
        "start_date": {"month": "3", "year": "2020"},
        "current": "false",
        "end_date": {"month": "6", "year": "2023"},
    }

    current = build_employment(
        WorkExperienceEntry(
            job_title="Lead",
            company="ACME",
            start_month=1,
            start_year=2024,
            is_current=True,
        )
    )
    assert current["current"] == "true"
    assert "end_date" not in current


def test_build_education_uses_greenhouse_date_shape() -> None:
    body = build_education(
        EducationEntry(
            school="Example University",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
            start_year=2016,
            end_year=2020,
        ),
        school_name_id="5417077",
        degree_id="5494452",
        discipline_id="5494865",
    )
    assert body["school_name_id"] == "5417077"
    assert body["start_date"] == {"month": "1", "year": "2016"}
    assert body["end_date"] == {"month": "6", "year": "2020"}


def test_build_employments_filters_incomplete_rows() -> None:
    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=1,
                start_year=2020,
            ),
            WorkExperienceEntry(job_title="Intern", company="ACME"),
        ]
    )
    assert len(build_employments(profile)) == 1


def test_resolver_uses_aliases_and_lookup() -> None:
    schools = load_json_fixture("greenhouse_education_schools.json")
    degrees = load_json_fixture("greenhouse_education_degrees.json")
    disciplines = load_json_fixture("greenhouse_education_disciplines.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/education/schools"):
            return httpx.Response(200, json=schools)
        if path.endswith("/education/degrees"):
            return httpx.Response(200, json=degrees)
        if path.endswith("/education/disciplines"):
            return httpx.Response(200, json=disciplines)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    resolver = GreenhouseEducationResolver(
        make_http_client(handler),
        "acme",
        {
            "education_id_aliases": {
                "degree:Master of Science": "5494453",
            }
        },
    )
    educations = resolver.resolve_all(
        ProfileData(
            education=[
                EducationEntry(
                    school="Example University",
                    degree="Bachelor of Science",
                    field_of_study="Computer Science",
                    start_year=2016,
                    end_year=2020,
                ),
                EducationEntry(
                    school="9999999",
                    degree="Master of Science",
                    field_of_study="Mathematics",
                    start_year=2020,
                    end_year=2022,
                ),
            ]
        )
    )
    assert len(educations) == 2
    assert educations[0]["school_name_id"] == "5417077"
    assert educations[1]["school_name_id"] == "9999999"


def test_build_application_payload_includes_structured_sections() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=3,
                start_year=2020,
                end_month=6,
                end_year=2023,
            )
        ],
        education=[
            EducationEntry(
                school="Example University",
                degree="5494452",
                field_of_study="5494865",
                start_year=2016,
                end_year=2020,
            )
        ],
    )
    payload = build_application_payload(
        profile,
        job_title="Senior Engineer",
        company="ACME",
        config={},
        employments=[
            {
                "company_name": "ACME",
                "title": "Engineer",
                "start_date": {"month": "3", "year": "2020"},
                "current": "false",
                "end_date": {"month": "6", "year": "2023"},
            }
        ],
        educations=[
            {
                "school_name_id": "5417077",
                "degree_id": "5494452",
                "discipline_id": "5494865",
                "start_date": {"month": "1", "year": "2016"},
                "end_date": {"month": "6", "year": "2020"},
            }
        ],
    )
    assert payload["employments"][0]["title"] == "Engineer"
    assert payload["educations"][0]["school_name_id"] == "5417077"


def test_dry_run_includes_structured_sections_from_profile() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=1,
                start_year=2020,
            )
        ],
        education=[
            EducationEntry(
                school="9999999",
                degree="5494452",
                field_of_study="5494865",
                start_year=2016,
                end_year=2020,
            )
        ],
    )
    applier = get_applier("greenhouse", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="5501001",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://boards.greenhouse.io/acme/jobs/5501001",
            config={"board_token": "acme"},
            profile=profile,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["employments"][0]["company_name"] == "ACME"
    assert result.payload["educations"][0]["school_name_id"] == "9999999"


def test_build_education_lookup_resolver_none_without_token() -> None:
    assert build_education_lookup_resolver(None, board_token=None, config={}) is None
    assert build_education_lookup_resolver(None, board_token="acme", config={}) is not None


def test_resolve_entry_returns_none_when_ids_or_year_missing() -> None:
    resolver = GreenhouseEducationResolver(None, "acme", {})
    # No numeric ids resolvable and lookups disabled (http None) → None.
    assert (
        resolver.resolve_entry(
            EducationEntry(school="Example", degree="BSc", field_of_study="CS", start_year=2016)
        )
        is None
    )


def test_resolve_id_uses_defaults_and_blank_and_digit() -> None:
    resolver = GreenhouseEducationResolver(
        None,
        "acme",
        {"default_degree_id": "111", "default_discipline_id": "222"},
    )
    entry = EducationEntry(
        school="5417077", degree="", field_of_study="", start_year=2016, end_year=2020
    )
    result = resolver.resolve_entry(entry)
    assert result is not None
    assert result["school_name_id"] == "5417077"
    assert result["degree_id"] == "111"
    assert result["discipline_id"] == "222"


def test_resolve_id_returns_none_when_lookup_disabled() -> None:
    resolver = GreenhouseEducationResolver(None, "acme", {"skip_education_lookup": True})
    assert resolver._resolve_id("school", "Example University") is None


def test_resolve_id_blank_value_returns_none() -> None:
    resolver = GreenhouseEducationResolver(None, "acme", {})
    assert resolver._resolve_id("school", "  ") is None


def test_fetch_candidates_caches_and_handles_http_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    resolver = GreenhouseEducationResolver(make_http_client(handler), "acme", {})
    first = resolver._fetch_candidates("school", "Example")
    second = resolver._fetch_candidates("school", "Example")
    assert first == []
    assert second == []
    assert calls["n"] == 1  # second call served from cache


def test_resolve_id_no_match_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    resolver = GreenhouseEducationResolver(make_http_client(handler), "acme", {})
    assert resolver._resolve_id("school", "Nonexistent School") is None


def test_parse_greenhouse_items_variants() -> None:
    assert _parse_greenhouse_items("nope") == []
    assert _parse_greenhouse_items({"items": "nope"}) == []
    assert _parse_greenhouse_items({"items": ["bad", {"id": 1, "text": "  "}, {"text": "x"}]}) == []
    assert _parse_greenhouse_items({"items": [{"id": 5, "text": "MIT"}]}) == [
        {"id": "5", "descriptor": "MIT"}
    ]


def test_config_default_id_variants() -> None:
    assert _config_default_id({"k": "1"}, "k") == "1"
    assert _config_default_id({}, "k") is None
