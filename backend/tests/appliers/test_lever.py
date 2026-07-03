"""Tests for the Lever apply adapter."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.lever import (
    LeverApplier,
    build_application_payload,
    build_urls,
    resolve_site,
)
from app.appliers.base import get_applier
from app.schemas.profile import (
    ApplyProfile,
    EducationEntry,
    ProfileData,
    ProfileLinks,
    ResumeFile,
    WorkExperienceEntry,
)
from tests.conftest import load_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(
            linkedin="https://linkedin.com/in/ada",
            github="https://github.com/ada",
            website="https://ada.example",
        ),
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"current_company": "Analytical Engines Ltd"},
    )


def test_resolve_site_from_config_or_url() -> None:
    assert resolve_site({"site": "acme"}, "") == "acme"
    assert (
        resolve_site({}, "https://jobs.lever.co/acme/33538a2f-d27d-4a96-8f05-fa4b0e4d940e")
        == "acme"
    )
    assert resolve_site({}, "https://example.com/jobs/1") is None


def test_build_urls_maps_profile_links() -> None:
    urls = build_urls(_profile().links)
    assert urls["LinkedIn"] == "https://linkedin.com/in/ada"
    assert urls["GitHub"] == "https://github.com/ada"
    assert urls["Portfolio"] == "https://ada.example"


def test_build_application_payload_maps_profile_fields() -> None:
    payload = build_application_payload(
        _profile(), job_title="Senior Engineer", company="ACME", config={"gdpr_consent": True}
    )
    assert payload["name"] == "Ada Lovelace"
    assert payload["email"] == "ada@example.com"
    assert payload["phone"] == "+1 555 0100"
    assert payload["org"] == "Analytical Engines Ltd"
    assert payload["urls"]["GitHub"] == "https://github.com/ada"
    assert "ACME" in payload["comments"]
    assert "Resume:" in payload["comments"]
    assert payload["consent"] == {"store": True, "marketing": False}


def test_build_application_payload_uses_cover_letter_override() -> None:
    payload = build_application_payload(
        _profile(),
        job_title="Senior Engineer",
        company="ACME",
        config={},
        cover_letter="Custom letter for ACME",
    )
    assert payload["comments"] == "Custom letter for ACME\n\nResume:\nExperienced engineer."


def test_build_application_payload_appends_structured_profile_supplement() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="ACME",
                start_month=3,
                start_year=2020,
            )
        ],
        education=[EducationEntry(school="Example University", start_year=2016, end_year=2020)],
        skills=["Python"],
    )
    payload = build_application_payload(
        profile, job_title="Senior Engineer", company="ACME", config={}
    )
    assert payload["comments"] is not None
    assert "Work experience:" in payload["comments"]
    assert "Education:" in payload["comments"]
    assert "Skills: Python" in payload["comments"]


def test_build_application_payload_can_skip_structured_profile_supplement() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        skills=["Python"],
    )
    payload = build_application_payload(
        profile,
        job_title="Senior Engineer",
        company="ACME",
        config={"skip_structured_profile": True},
    )
    assert payload.get("comments") is None


def test_build_application_payload_requires_name_and_email() -> None:
    try:
        build_application_payload(
            ProfileData(full_name="", email="ada@example.com"),
            job_title="Role",
            company="ACME",
            config={},
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "full_name" in str(exc)


def test_dry_run_returns_payload_without_network() -> None:
    applier = get_applier("lever", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="33538a2f-d27d-4a96-8f05-fa4b0e4d940e",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://jobs.lever.co/acme/33538a2f-d27d-4a96-8f05-fa4b0e4d940e",
            config={"site": "acme"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["email"] == "ada@example.com"
    assert result.error is None


def test_live_submit_posts_json_with_api_key_query() -> None:
    fixture = load_fixture("lever_apply_success.json")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, text=fixture, headers={"content-type": "application/json"})

    applier = LeverApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="33538a2f-d27d-4a96-8f05-fa4b0e4d940e",
            job_title="Senior Engineer",
            company="ACME",
            job_url="https://jobs.lever.co/acme/33538a2f-d27d-4a96-8f05-fa4b0e4d940e",
            config={"site": "acme", "postings_api_key": "lever-test-key"},
            profile=_profile(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert result.external_application_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert seen["method"] == "POST"
    url = seen["url"]
    assert isinstance(url, str)
    assert url.startswith(
        "https://api.lever.co/v0/postings/acme/33538a2f-d27d-4a96-8f05-fa4b0e4d940e"
    )
    assert "key=lever-test-key" in url
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["name"] == "Ada Lovelace"


def test_live_submit_uses_eu_host_when_configured() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "applicationId": "eu-1"})

    applier = LeverApplier(http=make_http_client(handler))
    applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"site": "acme", "region": "eu", "postings_api_key": "key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert seen["url"].startswith("https://api.eu.lever.co/v0/postings/acme/post-1")


def test_live_submit_prefers_credential_api_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "applicationId": "1"})

    applier = LeverApplier(http=make_http_client(handler))
    applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"site": "acme", "postings_api_key": "config-key"},
            profile=_profile(),
            credentials={
                "session": {"postings_api_key": "cred-key"},
                "cookies": {},
                "headers": {},
            },
            dry_run=False,
        )
    )
    assert "key=cred-key" in seen["url"]


def test_live_submit_uses_multipart_when_resume_file_present() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content_type"] = request.headers.get("content-type", "")
        seen["has_resume"] = b'name="resume"' in request.content
        return httpx.Response(200, json={"ok": True, "applicationId": "with-resume"})

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    applier = LeverApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"site": "acme", "postings_api_key": "key"},
            profile=profile,
            resume_file=resume,
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    content_type = seen["content_type"]
    assert isinstance(content_type, str)
    assert "multipart/form-data" in content_type
    assert seen["has_resume"] is True


def test_missing_api_key_fails_with_helpful_error() -> None:
    applier = get_applier("lever", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"site": "acme"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "Postings API key" in (result.error or "")
    assert result.payload is not None


def test_build_application_payload_uses_apply_profile_resume_file() -> None:
    resume = ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    payload = build_application_payload(profile, job_title="Role", company="ACME", config={})
    # resume_file arg omitted, so it is pulled from the ApplyProfile; resume text
    # is then excluded from comments.
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert "Resume:" not in (payload.get("comments") or "")


def test_apply_without_site_fails() -> None:
    applier = get_applier("lever", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="https://example.com/jobs/1",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "config.site" in (result.error or "")


def test_apply_fails_when_payload_build_raises() -> None:
    applier = get_applier("lever", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"site": "acme"},
            profile=ProfileData(full_name="", email="a@example.com"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "full_name" in (result.error or "")


def test_build_application_payload_requires_email() -> None:
    try:
        build_application_payload(
            ProfileData(full_name="Ada", email=""),
            job_title="Role",
            company="ACME",
            config={},
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "email" in str(exc)


def test_build_application_payload_silent_and_compliance_and_url_answers() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={
            "current_company": "ACME",
            "blank": "",
            "other_answer": "ignored",
            "urls.Blog": "https://ada.blog",
        },
    )
    payload = build_application_payload(
        profile,
        job_title="Role",
        company="ACME",
        config={
            "silent_confirmations": True,
            "gdpr_consent": True,
            "compliance_policy_id": "policy-1",
        },
    )
    assert payload["silent"] is True
    assert payload["consent"]["store"]["compliancePolicyId"] == "policy-1"
    assert payload["urls"]["Blog"] == "https://ada.blog"


def test_live_submit_handles_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    applier = LeverApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"site": "acme", "postings_api_key": "key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None


def test_live_submit_surfaces_ok_false_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "duplicate"})

    applier = LeverApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="post-1",
            job_title="Role",
            company="ACME",
            job_url="",
            config={"site": "acme", "postings_api_key": "key"},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "duplicate"


def test_resolve_api_key_falls_back_to_config() -> None:
    from app.appliers.adapters.lever import resolve_api_key

    assert (
        resolve_api_key(
            {"session": {"postings_api_key": ""}, "cookies": {}, "headers": {}},
            {"postings_api_key": "config-key"},
        )
        == "config-key"
    )
    assert resolve_api_key(None, {}) is None


def test_extract_application_id_none() -> None:
    from app.appliers.adapters.lever import _extract_application_id

    assert _extract_application_id("nope") is None
    assert _extract_application_id({}) is None


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
