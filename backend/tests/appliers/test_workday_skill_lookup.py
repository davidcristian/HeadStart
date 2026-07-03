"""Tests for Workday skill lookup resolution."""

import httpx

from app.appliers.adapters.workday_skill_lookup import (
    SkillLookupResolver,
    build_skill_lookup_resolver,
)
from app.appliers.adapters.workday_skills import build_skill_body, preview_skills
from app.schemas.profile import ProfileData
from tests.appliers.workday_helpers import JOB_URL, WORKDAY_CREDENTIALS
from tests.conftest import load_json_fixture, make_http_client


def test_build_skill_body_uses_resolved_skill_id() -> None:
    body = build_skill_body("Python", skill={"id": "skill-wid"})
    assert body["skill"] == {"id": "skill-wid"}


def test_resolver_maps_skill_to_catalog_id() -> None:
    skill_fixture = load_json_fixture("workday_institutionvalues_skill.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/skill"):
            return httpx.Response(200, json=skill_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    target = _target()
    resolver = SkillLookupResolver(
        make_http_client(handler),
        target=target,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.skill_reference("Python") == {"id": "f1e2d3c4b5a697887766554433221100"}
    assert resolver.skill_reference("Unknown Skill") == {"descriptor": "Unknown Skill"}


def test_preview_skills_uses_lookup_when_resolver_available() -> None:
    skill_fixture = load_json_fixture("workday_institutionvalues_skill.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/institutionvalues/skill"):
            return httpx.Response(200, json=skill_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    target = _target()
    resolver = build_skill_lookup_resolver(
        make_http_client(handler),
        target=target,
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    previews = preview_skills(
        ProfileData(skills=["Python", "Unknown Skill"]),
        resolver=resolver,
    )
    assert previews[0]["skill"] == {"id": "f1e2d3c4b5a697887766554433221100"}
    assert previews[1]["skill"] == {"descriptor": "Unknown Skill"}


def test_resolver_honors_config_aliases_without_network() -> None:
    resolver = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={
            "skill_lookup_aliases": {
                "Python": "f1e2d3c4b5a697887766554433221100",
            }
        },
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.skill_reference("Python") == {"id": "f1e2d3c4b5a697887766554433221100"}


def test_resolver_skips_lookup_when_disabled() -> None:
    resolver = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="US-CA/Senior-Software-Engineer_JR1001",
        config={"skip_skill_lookup": True},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.skill_reference("Python") == {"descriptor": "Python"}


def test_skill_reference_empty_value_returns_none() -> None:
    resolver = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="loc/job",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.skill_reference("   ") is None


def test_skill_reference_workday_id_passthrough() -> None:
    wid = "f1e2d3c4b5a697887766554433221100"
    resolver = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="loc/job",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.skill_reference(wid) == {"id": wid}


def test_skill_reference_alias_workday_id_and_descriptor() -> None:
    wid = "f1e2d3c4b5a697887766554433221100"
    resolver = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="loc/job",
        config={"skill_lookup_aliases": {"kotlin": "Kotlin Lang"}},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    # Alias normalized lookup that maps to a plain descriptor.
    assert resolver.skill_reference("Kotlin") == {"descriptor": "Kotlin Lang"}
    resolver_id = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="loc/job",
        config={"skill_lookup_aliases": {"Go": wid}},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver_id.skill_reference("Go") == {"id": wid}


def test_skill_reference_caches_and_handles_http_error() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500, text="boom")

    resolver = SkillLookupResolver(
        make_http_client(handler),
        target=_target(),
        job_path="loc/job",
        config={},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    # HTTP error -> descriptor fallback and cached empty candidates.
    assert resolver.skill_reference("Rust") == {"descriptor": "Rust"}
    assert resolver.skill_reference("Rust") == {"descriptor": "Rust"}
    assert len(calls) == 1


def test_build_skill_lookup_resolver_requires_http_and_target() -> None:
    assert (
        build_skill_lookup_resolver(
            None,
            target=_target(),
            job_path="loc/job",
            config={},
            csrf_token="csrf",
            session_id="sess",
            credentials=WORKDAY_CREDENTIALS,
        )
        is None
    )
    assert (
        build_skill_lookup_resolver(
            make_http_client(_unexpected_request),
            target=None,
            job_path="loc/job",
            config={},
            csrf_token="csrf",
            session_id="sess",
            credentials=WORKDAY_CREDENTIALS,
        )
        is None
    )
    assert (
        build_skill_lookup_resolver(
            make_http_client(_unexpected_request),
            target=_target(),
            job_path="loc/job",
            config={},
            csrf_token=None,
            session_id="sess",
            credentials=None,
        )
        is None
    )


def test_config_alias_returns_none_without_match() -> None:
    resolver = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="loc/job",
        config={"skill_lookup_aliases": {"other": "x"}, "skip_skill_lookup": True},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    # No alias match and lookup disabled -> plain descriptor.
    assert resolver.skill_reference("Python") == {"descriptor": "Python"}


def test_config_alias_not_a_dict() -> None:
    resolver = SkillLookupResolver(
        make_http_client(_unexpected_request),
        target=_target(),
        job_path="loc/job",
        config={"skill_lookup_aliases": "nope", "skip_skill_lookup": True},
        csrf_token="csrf",
        session_id="sess",
        credentials=WORKDAY_CREDENTIALS,
    )
    assert resolver.skill_reference("Python") == {"descriptor": "Python"}


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
