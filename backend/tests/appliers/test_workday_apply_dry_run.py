"""Dry-run tests for the Workday apply adapter."""

import httpx

from app.appliers import ApplyContext
from app.appliers.base import get_applier
from app.schemas.profile import (
    EducationEntry,
    LanguageEntry,
    ProfileData,
    ResumeFile,
    WorkExperienceEntry,
)
from tests.appliers.workday_helpers import JOB_URL, WORKDAY_CREDENTIALS
from tests.conftest import load_json_fixture, make_http_client


def test_dry_run_returns_payload_with_questionnaire_preview() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                answers={"q-work-auth": "Yes"},
            ),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["candidate"]["emailAddress"] == "ada@example.com"
    assert "questionnaires" in result.payload
    assert result.error is None


def test_dry_run_includes_experience_and_education_preview() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
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
                education=[EducationEntry(school="Example University")],
                skills=["Python"],
                languages=[LanguageEntry(language="English", proficiency="Native")],
            ),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["workExperiences"][0]["companyName"] == "ACME"
    assert result.payload["educations"][0]["schoolName"] == "Example University"
    assert result.payload["skills"][0]["skill"]["descriptor"] == "Python"
    assert result.payload["languages"][0]["language"]["descriptor"] == "English"


def test_dry_run_resolves_education_lookups_when_credentials_present() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")
    degree_fixture = load_json_fixture("workday_institutionvalues_degree.json")
    field_fixture = load_json_fixture("workday_institutionvalues_field_of_study.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        if request.url.path.endswith("/institutionvalues/degree"):
            return httpx.Response(200, json=degree_fixture)
        if request.url.path.endswith("/institutionvalues/fieldOfStudy"):
            return httpx.Response(200, json=field_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                education=[
                    EducationEntry(
                        school="Example University",
                        degree="Bachelor of Science",
                        field_of_study="Computer Science",
                    )
                ],
            ),
            credentials=WORKDAY_CREDENTIALS,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["educations"][0]["degree"] == {"id": "a1b2c3d4e5f6478990a1b2c3d4e5f678"}
    assert result.payload["educations"][0]["fieldOfStudy"] == {
        "id": "d4e5f6478990a1b2c3d4e5f678012345"
    }


def test_dry_run_resolves_skill_lookups_when_credentials_present() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")
    skill_fixture = load_json_fixture("workday_institutionvalues_skill.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        if request.url.path.endswith("/institutionvalues/skill"):
            return httpx.Response(200, json=skill_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                skills=["Python"],
            ),
            credentials=WORKDAY_CREDENTIALS,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["skills"][0]["skill"] == {
        "id": "f1e2d3c4b5a697887766554433221100"
    }


def test_dry_run_includes_resume_attachment_preview() -> None:
    questionnaire_fixture = load_json_fixture("workday_questionnaire.json")
    posting_fixture = load_json_fixture("workday_job_posting_info.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/job/US-CA-Santa-Clara/Senior-Software-Engineer_JR1001"):
            return httpx.Response(200, json=posting_fixture)
        if request.url.path.endswith("/questionnaire/quest-primary-001"):
            return httpx.Response(200, json=questionnaire_fixture)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    applier = get_applier("workday", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="JR1001",
            job_title="Senior Software Engineer",
            company="ACME",
            job_url=JOB_URL,
            config={
                "tenant": "acme",
                "site": "AcmeCareers",
                "region": "wd5",
                "skip_secondary_questionnaire": True,
            },
            profile=ProfileData(
                full_name="Ada Lovelace",
                email="ada@example.com",
                answers={"q-work-auth": "Yes"},
            ),
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["resumeAttachments"]["attachments"][0]["fileName"] == "resume.pdf"
    assert "Resume:" not in str(result.payload.get("candidate", {}).get("comments", ""))
