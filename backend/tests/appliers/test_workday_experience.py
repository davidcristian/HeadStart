"""Tests for Workday work-experience and education helpers."""

import httpx

from app.appliers.adapters.workday_experience import (
    _response_error,
    applicable_education,
    applicable_work_experience,
    build_education_body,
    build_work_experience_body,
    preview_educations,
    preview_work_experiences,
    submit_educations,
    submit_work_experiences,
)
from app.schemas.profile import EducationEntry, ProfileData, WorkExperienceEntry
from tests.appliers.workday_helpers import JOB_URL
from tests.conftest import load_json_fixture, make_http_client


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")


def test_build_work_experience_body_maps_dates_and_current_role() -> None:
    body = build_work_experience_body(
        WorkExperienceEntry(
            job_title="Engineer",
            company="ACME",
            location="Remote",
            start_month=3,
            start_year=2020,
            end_month=6,
            end_year=2023,
            description="Built APIs",
        )
    )
    assert body == {
        "jobTitle": "Engineer",
        "companyName": "ACME",
        "currentlyWorkHere": False,
        "startDate": "2020-03-01",
        "location": "Remote",
        "roleDescription": "Built APIs",
        "endDate": "2023-06-01",
    }


def test_build_work_experience_body_omits_end_date_for_current_role() -> None:
    body = build_work_experience_body(
        WorkExperienceEntry(
            job_title="Lead",
            company="ACME",
            start_month=1,
            start_year=2024,
            is_current=True,
        )
    )
    assert body["currentlyWorkHere"] is True
    assert "endDate" not in body


def test_build_education_body_maps_school_and_years() -> None:
    body = build_education_body(
        EducationEntry(
            school="Example University",
            degree="Bachelor of Science",
            field_of_study="Computer Science",
            start_year=2016,
            end_year=2020,
            gpa="3.8",
        )
    )
    assert body == {
        "schoolName": "Example University",
        "degree": {"descriptor": "Bachelor of Science"},
        "fieldOfStudy": {"descriptor": "Computer Science"},
        "firstYearAttended": "2016-01-01",
        "lastYearAttended": "2020-01-01",
        "gradeAverage": "3.8",
    }


def test_applicable_rows_require_minimum_fields() -> None:
    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=1,
                start_year=2020,
            ),
            WorkExperienceEntry(job_title="Incomplete", company=""),
        ],
        education=[
            EducationEntry(school="Example U"),
            EducationEntry(school=""),
        ],
    )
    assert len(applicable_work_experience(profile)) == 1
    assert len(applicable_education(profile)) == 1
    assert len(preview_work_experiences(profile)) == 1
    assert len(preview_educations(profile)) == 1


def test_submit_work_experiences_posts_each_row() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.method == "POST"
        body = request.read().decode()
        assert "Engineer" in body
        return httpx.Response(200, json={"id": f"exp-{len(seen)}"})

    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=1,
                start_year=2020,
            )
        ]
    )
    results = submit_work_experiences(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert len(results) == 1
    assert results[0].ok
    assert seen == ["/wday/cxs/acme/jobapplication/app-1/workexperiences"]


def test_submit_educations_stops_on_workday_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/degree"):
            return httpx.Response(200, json={"total": 0, "data": []})
        if request.url.path.endswith("/educations"):
            return httpx.Response(
                200,
                json={"errorCode": "VALIDATION_FAILED", "message": "Invalid degree"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    profile = ProfileData(education=[EducationEntry(school="Example U", degree="BS")])
    results = submit_educations(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error == "Invalid degree"


def test_submit_educations_posts_resolved_degree_id() -> None:
    degree_fixture = load_json_fixture("workday_institutionvalues_degree.json")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/degree"):
            return httpx.Response(200, json=degree_fixture)
        if request.url.path.endswith("/institutionvalues/fieldOfStudy"):
            return httpx.Response(200, json={"total": 0, "data": []})
        if request.url.path.endswith("/educations"):
            seen.append(request.read().decode())
            return httpx.Response(200, json={"id": "edu-1"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    profile = ProfileData(
        education=[
            EducationEntry(
                school="Example U",
                degree="Bachelor of Science",
            )
        ]
    )
    results = submit_educations(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert len(results) == 1
    assert results[0].ok
    assert results[0].payload["degree"] == {"id": "a1b2c3d4e5f6478990a1b2c3d4e5f678"}
    assert "a1b2c3d4e5f6478990a1b2c3d4e5f678" in seen[0]


def test_submit_work_experiences_skipped_by_config() -> None:
    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(job_title="Eng", company="ACME", start_month=1, start_year=2020)
        ]
    )
    assert (
        submit_work_experiences(
            make_http_client(_unexpected),
            target=_target(),
            application_id="app-1",
            profile=profile,
            job_path="loc/job",
            config={"skip_work_experience": True},
            csrf_token="csrf",
            session_id="sess",
            credentials=None,
        )
        == []
    )


def test_submit_work_experiences_stops_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(job_title="Eng", company="ACME", start_month=1, start_year=2020)
        ]
    )
    results = submit_work_experiences(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path="loc/job",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert len(results) == 1
    assert results[0].ok is False


def test_submit_work_experiences_stops_on_workday_error_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errorCode": "X", "message": "bad row"})

    profile = ProfileData(
        work_experience=[
            WorkExperienceEntry(job_title="Eng", company="ACME", start_month=1, start_year=2020)
        ]
    )
    results = submit_work_experiences(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path="loc/job",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert results[0].error == "bad row"


def test_submit_educations_skipped_by_config() -> None:
    profile = ProfileData(education=[EducationEntry(school="Example U")])
    assert (
        submit_educations(
            make_http_client(_unexpected),
            target=_target(),
            application_id="app-1",
            profile=profile,
            job_path="loc/job",
            config={"skip_education": True},
            csrf_token="csrf",
            session_id="sess",
            credentials=None,
        )
        == []
    )


def test_submit_educations_stops_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/degree"):
            return httpx.Response(200, json={"total": 0, "data": []})
        if request.url.path.endswith("/institutionvalues/fieldOfStudy"):
            return httpx.Response(200, json={"total": 0, "data": []})
        return httpx.Response(500, text="boom")

    profile = ProfileData(education=[EducationEntry(school="Example U", degree="BS")])
    results = submit_educations(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path="loc/job",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=None,
    )
    assert len(results) == 1
    assert results[0].ok is False


def test_response_error_variants() -> None:
    assert _response_error("not-a-dict") is None
    assert _response_error({"ok": True}) is None
    assert _response_error({"errors": [{"error": "field bad"}]}) == "field bad"
    assert _response_error({"errors": [{"code": "E1"}]}) == "E1"
    assert _response_error({"errors": [{}]}) == "{}"
    assert _response_error({"errors": ["scalar-error"]}) is None
    assert _response_error({"errors": []}) is None


def _target():
    from app.appliers.adapters.workday_common import resolve_target

    target = resolve_target(
        {"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
        JOB_URL,
    )
    assert target is not None
    return target
