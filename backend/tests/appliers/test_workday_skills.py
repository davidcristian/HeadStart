"""Tests for Workday skills and languages helpers."""

import json

import httpx

from app.appliers.adapters.workday_skills import (
    applicable_languages,
    applicable_skills,
    build_language_body,
    build_skill_body,
    preview_languages,
    preview_skills,
    submit_languages,
    submit_skills,
)
from app.schemas.profile import LanguageEntry, ProfileData
from tests.appliers.workday_helpers import JOB_URL, WORKDAY_CREDENTIALS
from tests.conftest import load_json_fixture, make_http_client


def test_build_skill_body_uses_descriptor() -> None:
    assert build_skill_body("Python") == {"skill": {"descriptor": "Python"}}


def test_build_language_body_maps_native_and_proficiency() -> None:
    assert build_language_body(
        LanguageEntry(language="English", proficiency="Fluent", is_native=True)
    ) == {
        "language": {"descriptor": "English"},
        "native": True,
        "languageProficiency": {"descriptor": "Fluent"},
    }


def test_build_language_body_omits_optional_fields() -> None:
    assert build_language_body(LanguageEntry(language="Spanish")) == {
        "language": {"descriptor": "Spanish"},
    }


def test_applicable_rows_require_minimum_fields() -> None:
    profile = ProfileData(
        skills=["Python", "  ", ""],
        languages=[
            LanguageEntry(language="English"),
            LanguageEntry(language=""),
        ],
    )
    assert applicable_skills(profile) == ["Python"]
    assert len(applicable_languages(profile)) == 1
    assert len(preview_skills(profile)) == 1
    assert len(preview_languages(profile)) == 1


def test_submit_skills_posts_each_row() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/skill"):
            return httpx.Response(200, json={"total": 0, "data": []})
        seen.append(request.url.path)
        assert request.method == "POST"
        return httpx.Response(200, json={"id": f"skill-{len(seen)}"})

    profile = ProfileData(skills=["Python", "SQL"])
    results = submit_skills(
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
    assert len(results) == 2
    assert all(result.ok for result in results)
    assert seen == [
        "/wday/cxs/acme/jobapplication/app-1/skills",
        "/wday/cxs/acme/jobapplication/app-1/skills",
    ]


def test_submit_skills_resolves_catalog_ids_when_credentials_present() -> None:
    skill_fixture = load_json_fixture("workday_institutionvalues_skill.json")
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/skill"):
            return httpx.Response(200, json=skill_fixture)
        if request.url.path.endswith("/skills"):
            seen.append(json.loads(request.read().decode()))
            return httpx.Response(200, json={"id": f"skill-{len(seen)}"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    profile = ProfileData(skills=["Python"])
    results = submit_skills(
        make_http_client(handler),
        target=_target(),
        application_id="app-1",
        profile=profile,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert len(results) == 1
    assert results[0].ok
    assert seen[0]["skill"] == {"id": "f1e2d3c4b5a697887766554433221100"}


def test_submit_languages_stops_on_workday_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/languages"):
            return httpx.Response(
                200,
                json={"errorCode": "VALIDATION_FAILED", "message": "Unknown language"},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    profile = ProfileData(languages=[LanguageEntry(language="Klingon", proficiency="Fluent")])
    results = submit_languages(
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
    assert results[0].error == "Unknown language"


def _target():
    from app.appliers.adapters.workday_common import resolve_target

    target = resolve_target(
        {"tenant": "acme", "site": "AcmeCareers", "region": "wd5"},
        JOB_URL,
    )
    assert target is not None
    return target
