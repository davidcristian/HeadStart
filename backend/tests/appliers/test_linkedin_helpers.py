"""Unit tests for LinkedIn apply helper modules (common, detail, form, route)."""

from __future__ import annotations

import pytest
from _pytest.monkeypatch import MonkeyPatch

from app.appliers.adapters.linkedin_common import (
    build_graphql_url,
    build_graphql_variables_string,
    decode_linkedin_redirect,
    extract_code_comment,
    has_linkedin_session_cookies,
    resolve_csrf_token,
    resolve_job_posting_url,
    voyager_request_cookies,
    voyager_request_headers,
)
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
from app.appliers.adapters.linkedin_route import resolve_apply_route

# --- resolve_job_posting_url -------------------------------------------------


def test_resolve_job_posting_url_uses_numeric_id() -> None:
    url = resolve_job_posting_url("4434410881", "")
    assert url.endswith("/jobPosting/4434410881")


def test_resolve_job_posting_url_falls_back_to_view_url() -> None:
    url = resolve_job_posting_url(
        "",
        "https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529",
    )
    assert url.endswith("/jobPosting/4432008529")


def test_resolve_job_posting_url_view_url_without_id_raises() -> None:
    with pytest.raises(ValueError, match="numeric job id"):
        resolve_job_posting_url(
            "",
            "https://www.linkedin.com/jobs/view/python-developer-at-cgi",
        )


def test_resolve_job_posting_url_non_linkedin_url_raises() -> None:
    with pytest.raises(ValueError, match="numeric job id"):
        resolve_job_posting_url("", "https://example.com/careers/some-role")


def test_resolve_job_posting_url_empty_inputs_raise() -> None:
    with pytest.raises(ValueError):
        resolve_job_posting_url("", "")


# --- extract_code_comment ----------------------------------------------------


def test_extract_code_comment_reads_value() -> None:
    html = '<code id="referenceId"><!--"abc123=="--></code>'
    assert extract_code_comment(html, "referenceId") == "abc123=="


def test_extract_code_comment_missing_marker() -> None:
    assert extract_code_comment("<div></div>", "referenceId") is None


def test_extract_code_comment_no_comment_after_marker() -> None:
    html = '<code id="referenceId">no comment here</code>'
    assert extract_code_comment(html, "referenceId") is None


def test_extract_code_comment_unterminated_comment() -> None:
    html = '<code id="referenceId"><!--dangling'
    assert extract_code_comment(html, "referenceId") is None


def test_extract_code_comment_empty_value_returns_none() -> None:
    html = '<code id="referenceId"><!--  --></code>'
    assert extract_code_comment(html, "referenceId") is None


def test_extract_code_comment_non_matching_regex() -> None:
    # Comment present but regex cannot pull a value (empty between markers)
    html = '<code id="referenceId"><!----></code>'
    assert extract_code_comment(html, "referenceId") is None


# --- decode_linkedin_redirect ------------------------------------------------


def test_decode_linkedin_redirect_empty_string() -> None:
    assert decode_linkedin_redirect("   ") == ""


def test_decode_linkedin_redirect_unwraps_target() -> None:
    wrapped = (
        "https://www.linkedin.com/redir/redirect?url="
        "https%3A%2F%2Fboards.greenhouse.io%2Facme%2Fjobs%2F1"
    )
    assert decode_linkedin_redirect(wrapped) == "https://boards.greenhouse.io/acme/jobs/1"


def test_decode_linkedin_redirect_no_url_param_returns_input() -> None:
    wrapped = "https://www.linkedin.com/redir/redirect?other=1"
    assert decode_linkedin_redirect(wrapped) == wrapped


def test_decode_linkedin_redirect_plain_url_passthrough() -> None:
    plain = "https://example.com/apply"
    assert decode_linkedin_redirect(plain) == plain


# --- session cookie / csrf helpers -------------------------------------------


def test_has_linkedin_session_cookies_variants() -> None:
    assert has_linkedin_session_cookies(None) is False
    assert has_linkedin_session_cookies({"cookies": {}}) is False
    assert has_linkedin_session_cookies({"cookies": {"li_at": "x"}}) is False
    assert has_linkedin_session_cookies({"cookies": {"li_at": "x", "JSESSIONID": "y"}}) is True


def test_resolve_csrf_token_from_session() -> None:
    creds = {"session": {"csrf_token": "ajax:token"}, "cookies": {}}
    assert resolve_csrf_token(creds) == "ajax:token"


def test_resolve_csrf_token_blank_session_value_falls_through() -> None:
    creds = {"session": {"csrf_token": "   "}, "cookies": {"JSESSIONID": '"raw-id"'}}
    assert resolve_csrf_token(creds) == "ajax:raw-id"


def test_resolve_csrf_token_from_jsessionid_already_ajax() -> None:
    creds = {"session": {}, "cookies": {"JSESSIONID": "ajax:existing"}}
    assert resolve_csrf_token(creds) == "ajax:existing"


def test_resolve_csrf_token_none_when_absent() -> None:
    assert resolve_csrf_token(None) is None
    assert resolve_csrf_token({"session": {}, "cookies": {}}) is None


# --- voyager headers / cookies -----------------------------------------------


def test_voyager_request_headers_without_credentials() -> None:
    headers = voyager_request_headers(None)
    assert "csrf-token" not in headers
    assert headers["x-restli-protocol-version"] == "2.0.0"


def test_voyager_request_headers_with_csrf_and_extra() -> None:
    creds = {
        "session": {"csrf_token": "ajax:t"},
        "cookies": {},
        "headers": {"X-Custom": "1"},
    }
    headers = voyager_request_headers(creds)
    assert headers["csrf-token"] == "ajax:t"
    assert headers["X-Custom"] == "1"
    assert headers["x-li-graphql-pegasus-client"] == "true"


def test_voyager_request_cookies() -> None:
    assert voyager_request_cookies(None) == {}
    assert voyager_request_cookies({"cookies": {"li_at": "x"}}) == {"li_at": "x"}


# --- graphql serialization ---------------------------------------------------


def test_build_graphql_variables_string_all_types() -> None:
    encoded = build_graphql_variables_string(
        {
            "flag": True,
            "off": False,
            "num": 5,
            "items": ["a b", 2],
        }
    )
    assert "flag:true" in encoded
    assert "off:false" in encoded
    assert "num:5" in encoded
    assert "List(a%20b,2)" in encoded


def test_build_graphql_url_with_query_name() -> None:
    url = build_graphql_url(
        query_id="qid",
        variables={"jobPostingUrn": "urn:1"},
        query_name="MyQuery",
    )
    assert "queryId=qid" in url
    assert "queryName=MyQuery" in url


def test_build_graphql_url_without_query_name() -> None:
    url = build_graphql_url(query_id="qid", variables={})
    assert "queryName" not in url


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


# --- route resolution edge cases ---------------------------------------------


def _detail(**overrides: object) -> LinkedInJobDetail:
    base: dict[str, object] = {
        "job_id": "1",
        "title": "T",
        "company": "C",
        "reference_id": None,
        "tracking_id": None,
        "easy_apply": False,
        "offsite_apply": False,
        "external_apply_url": None,
        "expired": False,
    }
    base.update(overrides)
    return LinkedInJobDetail(**base)  # type: ignore[arg-type]


def test_resolve_apply_route_expired() -> None:
    route = resolve_apply_route(_detail(expired=True))
    assert route.kind == "unsupported"
    assert "expired" in (route.reason or "")


def test_resolve_apply_route_external_registered_ats() -> None:
    route = resolve_apply_route(
        _detail(external_apply_url="https://boards.greenhouse.io/acme/jobs/5501001")
    )
    assert route.kind == "external_ats"
    assert route.adapter_key == "greenhouse"


def test_resolve_apply_route_external_ats_without_adapter(monkeypatch: MonkeyPatch) -> None:
    # An ATS URL that parses to a known target whose adapter is not registered.
    import app.appliers.adapters.linkedin_route as route_module

    monkeypatch.setattr(route_module, "has_applier", lambda key: False)
    route = resolve_apply_route(
        _detail(external_apply_url="https://boards.greenhouse.io/acme/jobs/5501001")
    )
    assert route.kind == "unsupported"
    assert route.adapter_key == "greenhouse"
    assert "no apply adapter" in (route.reason or "")


def test_resolve_apply_route_external_unrecognized_url() -> None:
    route = resolve_apply_route(
        _detail(external_apply_url="https://random-company.example/careers/apply")
    )
    assert route.kind == "unsupported"
    assert "not a supported ATS" in (route.reason or "")


def test_resolve_apply_route_easy_apply() -> None:
    route = resolve_apply_route(_detail(easy_apply=True))
    assert route.kind == "linkedin_hosted"
    assert route.adapter_key == "linkedin"


def test_resolve_apply_route_offsite_without_url() -> None:
    route = resolve_apply_route(_detail(offsite_apply=True))
    assert route.kind == "unsupported"
    assert "offsite apply URL was not found" in (route.reason or "")


def test_resolve_apply_route_no_signal() -> None:
    route = resolve_apply_route(_detail())
    assert route.kind == "unsupported"
    assert "no Easy Apply button" in (route.reason or "")
