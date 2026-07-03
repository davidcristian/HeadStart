"""Tests for Workday education submission and response-error helpers."""

import httpx

from app.appliers.adapters.workday_experience import (
    _response_error,
    submit_educations,
)
from app.schemas.profile import EducationEntry, ProfileData
from tests.appliers.workday_helpers import JOB_URL
from tests.conftest import load_json_fixture, make_http_client


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request: {request.method} {request.url}")


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
