"""Unit tests for LinkedIn apply detail + Easy Apply form helpers."""

from __future__ import annotations

import pytest

from app.appliers.adapters.linkedin_detail import (
    LinkedInJobDetail,
    extract_company_apply_url,
    merge_external_apply_url,
    parse_job_posting_page,
    reject_auth_wall,
)
from app.appliers.adapters.linkedin_easy_apply_form import (
    build_file_upload_responses,
    element_title,
    extract_form_root,
    form_has_file_upload_elements,
    is_file_upload_element,
    iter_form_elements,
    required_file_upload_titles,
)

# --- detail parsing edge cases -----------------------------------------------


def test_reject_auth_wall_raises_on_marker() -> None:
    with pytest.raises(ValueError, match="auth wall"):
        reject_auth_wall("Please Sign in to LinkedIn to continue")


def test_parse_job_posting_page_missing_title_returns_none() -> None:
    html = '<code id="decoratedJobPostingId"><!--"111"--></code>'
    assert parse_job_posting_page(html) is None


def test_parse_job_posting_page_expired_flag() -> None:
    html = (
        '<code id="decoratedJobPostingId"><!--"111"--></code>'
        '<h2 class="topcard__title">Engineer</h2>'
        "<p>No longer accepting applications</p>"
    )
    detail = parse_job_posting_page(html)
    assert detail is not None
    assert detail.expired is True


def test_parse_job_posting_page_offsite_button() -> None:
    html = (
        '<code id="decoratedJobPostingId"><!--"111"--></code>'
        '<h2 class="topcard__title">Engineer</h2>'
        '<a class="topcard__org-name-link">Acme</a>'
        '<button data-tracking-control-name="public_jobs_apply-link-offsite" '
        'data-tracking-id="trk-1">Apply</button>'
    )
    detail = parse_job_posting_page(html)
    assert detail is not None
    assert detail.offsite_apply is True
    assert detail.easy_apply is False
    assert detail.tracking_id == "trk-1"
    assert detail.company == "Acme"


def test_merge_external_apply_url_noop_when_empty() -> None:
    detail = LinkedInJobDetail(
        job_id="1",
        title="T",
        company="C",
        reference_id=None,
        tracking_id=None,
        easy_apply=False,
        offsite_apply=True,
        external_apply_url=None,
        expired=False,
    )
    assert merge_external_apply_url(detail, None) is detail


def test_merge_external_apply_url_attaches() -> None:
    detail = LinkedInJobDetail(
        job_id="1",
        title="T",
        company="C",
        reference_id="r",
        tracking_id="t",
        easy_apply=False,
        offsite_apply=True,
        external_apply_url=None,
        expired=False,
    )
    merged = merge_external_apply_url(detail, "https://x/apply")
    assert merged.external_apply_url == "https://x/apply"
    assert merged.reference_id == "r"


def test_extract_company_apply_url_direct() -> None:
    assert extract_company_apply_url({"companyApplyUrl": " https://x "}) == "https://x"


def test_extract_company_apply_url_via_apply_method() -> None:
    payload = {
        "data": {
            "jobsDashJobPostingsById": {
                "applyMethod": {
                    "com.linkedin.OffsiteApply": {"companyApplyUrl": "https://ats/apply"}
                }
            }
        }
    }
    assert extract_company_apply_url(payload) == "https://ats/apply"


def test_extract_company_apply_url_top_level_nested() -> None:
    payload = {"jobsDashJobPostingsById": {"companyApplyUrl": "https://top/apply"}}
    assert extract_company_apply_url(payload) == "https://top/apply"


def test_extract_company_apply_url_none() -> None:
    assert extract_company_apply_url({"data": {}}) is None


def test_extract_company_apply_url_offsite_without_url() -> None:
    payload = {"applyMethod": {"com.linkedin.OffsiteApply": {"other": 1}}}
    assert extract_company_apply_url(payload) is None


def test_extract_company_apply_url_skips_non_offsite_and_non_dict_methods() -> None:
    payload = {
        "applyMethod": {
            "com.linkedin.ComplexOnsiteApply": {"companyApplyUrl": "https://ignored"},
            "notADict": "value",
            "com.linkedin.OffsiteApply": {"companyApplyUrl": "https://ats/apply"},
        }
    }
    assert extract_company_apply_url(payload) == "https://ats/apply"


# --- form helpers ------------------------------------------------------------


def test_extract_form_root_bad_shapes() -> None:
    assert extract_form_root({"data": "not-a-dict"}) is None
    assert extract_form_root({"data": {}}) is None
    assert extract_form_root({"data": {"jobsDashOnsiteApplyApplicationByJobPosting": []}}) is None
    assert (
        extract_form_root(
            {"data": {"jobsDashOnsiteApplyApplicationByJobPosting": {"elements": []}}}
        )
        is None
    )
    assert (
        extract_form_root(
            {"data": {"jobsDashOnsiteApplyApplicationByJobPosting": {"elements": ["x"]}}}
        )
        is None
    )
    assert (
        extract_form_root(
            {
                "data": {
                    "jobsDashOnsiteApplyApplicationByJobPosting": {
                        "elements": [{"jobApplicationForms": []}]
                    }
                }
            }
        )
        is None
    )
    assert (
        extract_form_root(
            {
                "data": {
                    "jobsDashOnsiteApplyApplicationByJobPosting": {
                        "elements": [{"jobApplicationForms": ["not-dict"]}]
                    }
                }
            }
        )
        is None
    )


def test_iter_form_elements_skips_bad_shapes() -> None:
    form_root = {
        "questionGroupings": [
            "not-a-dict",
            {"formSection": "not-a-dict"},
            {
                "formSection": {
                    "formElementGroups": [
                        "not-a-dict",
                        {"formElements": ["not-dict", {"entityUrn": "u"}]},
                    ]
                }
            },
        ]
    }
    elements = iter_form_elements(form_root)
    assert elements == [{"entityUrn": "u"}]


def test_element_title_variants() -> None:
    assert element_title({"title": {"text": " Name "}}) == "Name"
    assert element_title({"title": {"text": 5}}) == ""
    assert element_title({"title": "plain"}) == ""
    assert element_title({}) == ""


def test_is_file_upload_element_variants() -> None:
    assert is_file_upload_element({"formComponentResolutionResult": "x"}) is False
    assert (
        is_file_upload_element(
            {"formComponentResolutionResult": {"documentUploadFormComponent": {}}}
        )
        is True
    )
    assert (
        is_file_upload_element(
            {"formComponentResolutionResult": {"singleLineTextFormComponent": {}}}
        )
        is False
    )


def test_build_file_upload_responses_skips_non_upload_and_urnless() -> None:
    form_root = {
        "questionGroupings": [
            {
                "formSection": {
                    "formElementGroups": [
                        {
                            "formElements": [
                                {
                                    "formComponentResolutionResult": {
                                        "singleLineTextFormComponent": {}
                                    }
                                },
                                {
                                    "formComponentResolutionResult": {
                                        "documentUploadFormComponent": {}
                                    }
                                },
                                {
                                    "entityUrn": "urn:file",
                                    "formComponentResolutionResult": {
                                        "documentUploadFormComponent": {}
                                    },
                                },
                            ]
                        }
                    ]
                }
            }
        ]
    }
    responses = build_file_upload_responses(form_root, asset_urn="a", filename="r.pdf")
    assert len(responses) == 1
    assert responses[0]["formElementUrn"] == "urn:file"


def test_required_file_upload_titles_uses_urn_fallback() -> None:
    form_root = {
        "questionGroupings": [
            {
                "formSection": {
                    "formElementGroups": [
                        {
                            "formElements": [
                                {
                                    "required": True,
                                    "entityUrn": "urn:file",
                                    "formComponentResolutionResult": {
                                        "documentUploadFormComponent": {}
                                    },
                                },
                                {
                                    "required": False,
                                    "entityUrn": "urn:skip",
                                    "formComponentResolutionResult": {
                                        "documentUploadFormComponent": {}
                                    },
                                },
                            ]
                        }
                    ]
                }
            }
        ]
    }
    assert required_file_upload_titles(form_root) == ["urn:file"]


def test_form_has_file_upload_elements_false() -> None:
    assert form_has_file_upload_elements({"questionGroupings": []}) is False
