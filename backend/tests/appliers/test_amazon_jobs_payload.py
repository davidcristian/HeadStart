"""Tests for Amazon Jobs detail parsing and payload builders."""

import httpx
import pytest

from app.appliers.adapters.amazon_jobs_detail import (
    AmazonJobDetail,
    fetch_public_job_detail,
)
from app.appliers.adapters.amazon_jobs_payload import (
    build_applicant_body,
    build_application_payload,
)
from app.schemas.profile import ProfileData, ProfileLinks
from tests.conftest import make_http_client

JOB_ID = "10410605"


def _detail() -> AmazonJobDetail:
    return AmazonJobDetail(
        job_id=JOB_ID,
        title="Engineer",
        company="Amazon",
        location="Redmond, WA",
        country_code="USA",
        apply_url="https://www.amazon.jobs/applicant/jobs/10410605/apply",
        account_apply_url="https://account.amazon.jobs/jobs/10410605/apply",
        raw={},
    )


def _client(payload: object) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        return httpx.Response(
            200, text=json.dumps(payload), headers={"content-type": "application/json"}
        )

    return make_http_client(handler)


def test_fetch_public_job_detail_rejects_non_dict_payload() -> None:
    with pytest.raises(ValueError, match="unexpected payload"):
        fetch_public_job_detail(_client([1, 2, 3]), locale="en", job_id=JOB_ID)


def test_fetch_public_job_detail_rejects_missing_jobs() -> None:
    with pytest.raises(ValueError, match="was not found"):
        fetch_public_job_detail(_client({"jobs": []}), locale="en", job_id=JOB_ID)


def test_fetch_public_job_detail_rejects_invalid_job_record() -> None:
    with pytest.raises(ValueError, match="invalid job record"):
        fetch_public_job_detail(_client({"jobs": ["nope"]}), locale="en", job_id=JOB_ID)


def test_fetch_public_job_detail_rejects_mismatched_id() -> None:
    with pytest.raises(ValueError, match="returned job 999"):
        fetch_public_job_detail(
            _client({"jobs": [{"id_icims": "999", "title": "X"}]}),
            locale="en",
            job_id=JOB_ID,
        )


def test_fetch_public_job_detail_uses_url_next_step_and_defaults() -> None:
    detail = fetch_public_job_detail(
        _client(
            {
                "jobs": [
                    {
                        "id_icims": JOB_ID,
                        "title": "Engineer",
                        "url_next_step": "https://apply.example/step",
                    }
                ]
            }
        ),
        locale="en",
        job_id=JOB_ID,
    )
    assert detail.apply_url == "https://apply.example/step"
    assert detail.company == "Amazon"
    assert detail.country_code is None


def test_fetch_public_job_detail_falls_back_to_apply_page_url() -> None:
    detail = fetch_public_job_detail(
        _client({"jobs": [{"id_icims": JOB_ID, "company_name": "AWS", "country_code": "US"}]}),
        locale="en",
        job_id=JOB_ID,
    )
    assert detail.apply_url.endswith(f"/applicant/jobs/{JOB_ID}/apply")
    assert detail.company == "AWS"
    assert detail.country_code == "US"


def test_build_applicant_body_requires_first_name() -> None:
    with pytest.raises(ValueError, match="full_name"):
        build_applicant_body(
            ProfileData(full_name="", email="a@example.com"),
            company="Amazon",
            job_title="Role",
        )


def test_build_applicant_body_requires_email() -> None:
    with pytest.raises(ValueError, match="email"):
        build_applicant_body(
            ProfileData(full_name="Ada", email=""),
            company="Amazon",
            job_title="Role",
        )


def test_build_applicant_body_minimal_profile_omits_optionals() -> None:
    body = build_applicant_body(
        ProfileData(full_name="Ada", email="a@example.com"),
        company="Amazon",
        job_title="Role",
    )
    applicant = body["applicant"]
    assert applicant["legal_last_name"] == "Ada"
    assert "primary_phone_number" not in applicant
    assert "location" not in applicant
    assert "linkedin_url" not in applicant
    assert "cover_letter" not in applicant


def test_build_applicant_body_includes_linkedin_and_skips_blank_answers() -> None:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="a@example.com",
        links=ProfileLinks(linkedin="https://linkedin.com/in/ada"),
        answers={"skip": "", "keep": "yes"},
    )
    body = build_applicant_body(profile, company="Amazon", job_title="Role")
    applicant = body["applicant"]
    assert applicant["linkedin_url"] == "https://linkedin.com/in/ada"
    assert "skip" not in applicant
    assert applicant["keep"] == "yes"


def test_build_applicant_body_uses_cover_letter_override() -> None:
    profile = ProfileData(full_name="Ada", email="a@example.com")
    body = build_applicant_body(
        profile, cover_letter="Custom letter", company="Amazon", job_title="Role"
    )
    assert body["applicant"]["cover_letter"] == "Custom letter"


def test_build_applicant_body_template_blank_yields_no_cover_letter() -> None:
    profile = ProfileData(full_name="Ada", email="a@example.com", cover_letter_template="   ")
    body = build_applicant_body(profile, company="Amazon", job_title="Role")
    assert "cover_letter" not in body["applicant"]


def test_build_application_payload_without_recruiting_source_or_resume() -> None:
    payload = build_application_payload(
        _detail(),
        ProfileData(full_name="Ada", email="a@example.com"),
        company="Amazon",
        job_title="Role",
    )
    assert payload["draft_application"]["body"] == {}
    assert "resume_upload" not in payload
    assert payload["job"]["job_id"] == JOB_ID
