"""Tests for the SmartRecruiters apply adapter."""

import json

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.smartrecruiters import SmartRecruitersApplier
from app.appliers.adapters.smartrecruiters_common import (
    auth_headers,
    resolve_company_id,
    resolve_posting_uuid,
    split_name,
)
from app.appliers.adapters.smartrecruiters_configuration import (
    consent_decisions,
    required_question_ids,
)
from app.appliers.adapters.smartrecruiters_payload import (
    build_application_payload,
    extract_application_id,
)
from app.appliers.adapters.smartrecruiters_questions import (
    build_screening_answers,
    missing_required_answers,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ApplyProfile, ProfileData, ProfileLinks, ResumeFile
from tests.conftest import load_json_fixture, make_http_client


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(
            linkedin="https://linkedin.com/in/ada",
            website="https://ada.example",
        ),
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={
            "sr_8fe4cfaf-7d0b-4224-998b-14a3085537bb": "Yes",
            "sr_03bf8a6a-ba81-479f-8048-05ce9ef083c0": "The Analytical Engine",
        },
    )


def _handlers() -> dict[str, object]:
    posting_detail = load_json_fixture("smartrecruiters_posting_detail.json")
    configuration = load_json_fixture("smartrecruiters_apply_configuration.json")
    success = load_json_fixture("smartrecruiters_apply_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/postings/744000120624847"):
            return httpx.Response(200, json=posting_detail)
        if "/configuration" in url:
            return httpx.Response(200, json=configuration)
        if url.endswith("/candidates"):
            return httpx.Response(200, json=success)
        return httpx.Response(404, text="not found")

    return {
        "handler": handler,
        "posting_detail": posting_detail,
        "configuration": configuration,
        "success": success,
    }


def test_has_applier_registers_smartrecruiters() -> None:
    assert has_applier("smartrecruiters")


def test_resolve_company_id_from_config_or_url() -> None:
    assert resolve_company_id({"company_id": "AcmeCorp"}, "") == "AcmeCorp"
    assert (
        resolve_company_id(
            {},
            "https://jobs.smartrecruiters.com/AcmeCorp/744000120624847-senior-engineer",
        )
        == "AcmeCorp"
    )
    assert resolve_company_id({}, "https://example.com/jobs/1") is None


def test_split_name_handles_single_token() -> None:
    assert split_name("Prince") == ("Prince", "Prince")
    assert split_name("Ada Lovelace") == ("Ada", "Lovelace")


def test_auth_headers_prefers_smart_token() -> None:
    headers = auth_headers(
        {"session": {"smart_token": "token-1", "access_token": "bearer-1"}},
        {},
    )
    assert headers == {"X-SmartToken": "token-1"}


def test_consent_decisions_single_model() -> None:
    configuration = load_json_fixture("smartrecruiters_apply_configuration.json")
    assert consent_decisions(configuration, {"gdpr_consent": True}) == {"SINGLE": True}


def test_build_screening_answers_maps_profile_fields() -> None:
    configuration = load_json_fixture("smartrecruiters_apply_configuration.json")
    answers = build_screening_answers(configuration, _profile().answers)
    by_id = {item["id"]: item for item in answers}
    assert by_id["8fe4cfaf-7d0b-4224-998b-14a3085537bb"]["records"][0]["fields"]["value"] == ["1"]
    assert by_id["03bf8a6a-ba81-479f-8048-05ce9ef083c0"]["records"][0]["fields"]["value"] == [
        "The Analytical Engine"
    ]


def test_missing_required_answers_detects_gaps() -> None:
    configuration = load_json_fixture("smartrecruiters_apply_configuration.json")
    missing = missing_required_answers(configuration, {})
    assert missing == ["8fe4cfaf-7d0b-4224-998b-14a3085537bb"]
    assert required_question_ids(configuration) == ["8fe4cfaf-7d0b-4224-998b-14a3085537bb"]


def test_build_application_payload_maps_profile_fields() -> None:
    configuration = load_json_fixture("smartrecruiters_apply_configuration.json")
    payload = build_application_payload(
        _profile(),
        company="ACME",
        job_title="Senior Engineer",
        config={"gdpr_consent": True},
        configuration=configuration,
    )
    assert payload["firstName"] == "Ada"
    assert payload["lastName"] == "Lovelace"
    assert payload["email"] == "ada@example.com"
    assert payload["phoneNumber"] == "+1 555 0100"
    assert payload["location"] == {"fullLocation": "London, UK"}
    assert payload["web"]["linkedIn"] == "https://linkedin.com/in/ada"
    assert "ACME" in payload["messageToHiringManager"]
    assert payload["consentDecisions"] == {"SINGLE": True}
    assert len(payload["answers"]) == 2


def test_build_application_payload_includes_resume_bytes() -> None:
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    payload = build_application_payload(
        profile,
        company="ACME",
        job_title="Senior Engineer",
        config={},
        configuration=None,
        include_file_bytes=True,
    )
    assert payload["resume"]["fileName"] == "resume.pdf"
    assert payload["resume"]["fileContent"]
    assert "Resume:" not in payload.get("messageToHiringManager", "")


def test_resolve_posting_uuid_fetches_detail() -> None:
    fixtures = _handlers()
    http = make_http_client(fixtures["handler"])
    posting_uuid = resolve_posting_uuid(
        {},
        "744000120624847",
        company_id="AcmeCorp",
        http=http,
    )
    assert posting_uuid == "9a79267a-1159-49ea-ac24-0a336fa6abdd"


def test_dry_run_resolves_uuid_and_builds_payload() -> None:
    fixtures = _handlers()
    http = make_http_client(fixtures["handler"])
    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Senior Software Engineer",
        company="ACME Corp",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=_profile(),
        dry_run=True,
    )
    result = SmartRecruitersApplier(http=http).apply(ctx)
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["posting_uuid"] == "9a79267a-1159-49ea-ac24-0a336fa6abdd"
    assert result.payload["candidate"]["firstName"] == "Ada"


def test_dry_run_with_token_includes_configuration_summary() -> None:
    fixtures = _handlers()
    http = make_http_client(fixtures["handler"])
    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Senior Software Engineer",
        company="ACME Corp",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp", "gdpr_consent": True},
        profile=_profile(),
        credentials={"session": {"smart_token": "secret-token"}},
        dry_run=True,
    )
    result = SmartRecruitersApplier(http=http).apply(ctx)
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["configuration_questions"] == 2
    assert result.payload["missing_required_question_ids"] == []


def test_live_submit_requires_token() -> None:
    fixtures = _handlers()
    http = make_http_client(fixtures["handler"])
    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Senior Software Engineer",
        company="ACME Corp",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp"},
        profile=_profile(),
        dry_run=False,
    )
    result = SmartRecruitersApplier(http=http).apply(ctx)
    assert result.status == "failed"
    assert result.error is not None
    assert "smart_token" in result.error


def test_live_submit_posts_candidate_payload() -> None:
    fixtures = _handlers()
    posted: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/postings/744000120624847"):
            return httpx.Response(200, json=fixtures["posting_detail"])
        if "/configuration" in url:
            assert request.headers.get("X-SmartToken") == "secret-token"
            return httpx.Response(200, json=fixtures["configuration"])
        if url.endswith("/candidates"):
            posted.append(json.loads(request.content.decode()))
            return httpx.Response(200, json=fixtures["success"])
        return httpx.Response(404, text="not found")

    http = make_http_client(handler)
    ctx = ApplyContext(
        job_external_id="744000120624847",
        job_title="Senior Software Engineer",
        company="ACME Corp",
        job_url="https://jobs.smartrecruiters.com/AcmeCorp/744000120624847",
        config={"company_id": "AcmeCorp", "gdpr_consent": True},
        profile=_profile(),
        credentials={"session": {"smart_token": "secret-token"}},
        dry_run=False,
    )
    result = SmartRecruitersApplier(http=http).apply(ctx)
    assert result.status == "submitted"
    assert result.external_application_id == "application-456"
    assert posted
    assert posted[0]["email"] == "ada@example.com"
    assert posted[0]["answers"]


def test_get_applier_returns_smartrecruiters_instance() -> None:
    applier = get_applier("smartrecruiters")
    assert isinstance(applier, SmartRecruitersApplier)


def test_extract_application_id_reads_response_fields() -> None:
    assert extract_application_id({"applicationId": "app-1"}) == "app-1"
    assert extract_application_id({"id": "cand-1"}) == "cand-1"
