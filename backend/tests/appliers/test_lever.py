"""Tests for the Lever apply adapter: payload builders and pure helpers."""

from app.appliers.adapters.lever import (
    build_application_payload,
    build_urls,
    resolve_site,
)
from app.schemas.profile import (
    ApplyProfile,
    EducationEntry,
    ProfileData,
    ProfileLinks,
    ResumeFile,
    WorkExperienceEntry,
)


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
