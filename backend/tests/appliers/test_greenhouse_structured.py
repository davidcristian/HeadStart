"""Tests for Greenhouse structured profile mapping."""

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.greenhouse import build_application_payload
from app.appliers.adapters.greenhouse_structured import (
    GreenhouseEducationResolver,
    build_education,
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
