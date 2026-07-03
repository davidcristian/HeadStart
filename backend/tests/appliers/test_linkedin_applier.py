"""Flow-level tests for the LinkedIn applier covering error and edge branches."""

from __future__ import annotations

import httpx
from _pytest.monkeypatch import MonkeyPatch

from app.appliers import ApplyContext
from app.appliers.adapters.linkedin import (
    LinkedInApplier,
    _detail_from_override,
    _extract_application_id,
)
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client

EASY_APPLY_URL = "https://www.linkedin.com/jobs/view/quantitative-trader-at-example-co-4434410881"


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+1 555 0100",
        "location": "Remote",
        "resume_text": "Experienced engineer.",
        "cover_letter_template": "Dear {company}, I am excited about {job_title}.",
    }
    base.update(overrides)
    return ProfileData(**base)


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"li_at": "test", "JSESSIONID": "ajax:1"},
        "session": {"csrf_token": "ajax:1"},
        "headers": {},
    }


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")


# --- apply() top-level branches ----------------------------------------------


def test_apply_resolve_detail_value_error() -> None:
    # Empty external id + non-linkedin URL -> resolve_job_posting_url raises ValueError.
    applier = LinkedInApplier(http=make_http_client(_unexpected))
    result = applier.apply(
        ApplyContext(
            job_external_id="",
            job_title="Trader",
            company="Example Co",
            job_url="https://example.com/careers/some-role",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "numeric job id" in (result.error or "")


def test_apply_unsupported_route_payload() -> None:
    # Offsite listing with no external URL and not logged in -> unsupported route.
    fixture = load_fixture("linkedin_job_offsite.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4432008529",
            job_title="Python Developer",
            company="CGI",
            job_url="https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529",
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.payload is not None
    assert result.payload["route"] == "unsupported"
    assert result.payload["offsite_apply"] is True


# --- _delegate: payload None branch ------------------------------------------


def test_delegate_wraps_none_payload(monkeypatch: MonkeyPatch) -> None:
    from app.appliers.adapters import linkedin as linkedin_module
    from app.appliers.types import ApplyResult

    class _Stub:
        def apply(self, ctx: ApplyContext) -> ApplyResult:
            return ApplyResult(status="submitted", payload=None, external_application_id="x")

    monkeypatch.setattr(linkedin_module, "get_applier", lambda key, http=None: _Stub())
    applier = LinkedInApplier(http=make_http_client(_unexpected))
    result = applier.apply(
        ApplyContext(
            job_external_id="4432008529",
            job_title="Python Developer",
            company="CGI",
            job_url="https://www.linkedin.com/jobs/view/python-developer-at-cgi-4432008529",
            config={"external_apply_url": "https://boards.greenhouse.io/acme/jobs/1"},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "submitted"
    assert result.payload is not None
    assert result.payload["linkedin_route"] == "external_ats"
    assert result.payload["delegated_payload"] is None


# --- _apply_hosted branches --------------------------------------------------


def _hosted_handler() -> object:
    """Serve the Easy Apply job page but no session-gated form (not logged in)."""
    viewjob = load_fixture("linkedin_job_easy_apply.html")

    def handler(request: httpx.Request) -> httpx.Response:
        if "jobs-guest/jobs/api/jobPosting" in str(request.url):
            return httpx.Response(200, text=viewjob)
        raise AssertionError(f"unexpected {request.url}")

    return handler


def test_apply_hosted_build_payload_value_error() -> None:
    # Missing email -> build_easy_apply_payload raises ValueError inside _apply_hosted.
    applier = LinkedInApplier(http=make_http_client(_hosted_handler()))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(email=""),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "email" in (result.error or "")


def test_apply_hosted_live_requires_session_cookies() -> None:
    applier = LinkedInApplier(http=make_http_client(_hosted_handler()))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "session cookies" in (result.error or "")


def test_apply_hosted_live_form_not_loaded() -> None:
    # Logged in, but the form fetch returns something unparseable (form_root None).
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=load_fixture("linkedin_job_easy_apply.html"))
        if "voyager/api/graphql" in url:
            return httpx.Response(
                200, json={"data": {}}, headers={"content-type": "application/json"}
            )
        raise AssertionError(f"unexpected {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "could not load the application form" in (result.error or "")


def test_apply_hosted_live_missing_required_fields() -> None:
    # Form has a required field the profile cannot map -> missing_required_fields.
    form = load_fixture("linkedin_easy_apply_form_with_resume.json")
    profile = _profile(full_name="Ada", email="ada@example.com", phone="", location="")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=load_fixture("linkedin_job_easy_apply.html"))
        if "voyager/api/graphql" in url:
            return httpx.Response(200, text=form, headers={"content-type": "application/json"})
        raise AssertionError(f"unexpected {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=profile,
            credentials=_credentials(),
            dry_run=False,
        )
    )
    # Last name blank -> "Last name" required field is unmapped.
    assert result.status == "failed"
    assert "required questions" in (result.error or "")


def test_apply_hosted_live_requires_resume_upload() -> None:
    # Form requires a resume upload but no resume file is supplied.
    form = load_fixture("linkedin_easy_apply_form_with_resume.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=load_fixture("linkedin_job_easy_apply.html"))
        if "voyager/api/graphql" in url:
            return httpx.Response(200, text=form, headers={"content-type": "application/json"})
        raise AssertionError(f"unexpected {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "requires a resume file upload" in (result.error or "")


def test_apply_hosted_live_resume_from_profile_attr() -> None:
    # resume_file comes from profile.resume_file (ctx.resume_file is None).
    form = load_fixture("linkedin_easy_apply_form_with_resume.json")
    upload_meta = load_fixture("linkedin_media_upload_resume.json")
    apply_success = load_fixture("linkedin_apply_submit_success.json")
    resume = _resume()
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=load_fixture("linkedin_job_easy_apply.html"))
        if "voyager/api/graphql" in url:
            return httpx.Response(200, text=form, headers={"content-type": "application/json"})
        if "voyagerMediaUploadMetadata" in url:
            return httpx.Response(
                200, text=upload_meta, headers={"content-type": "application/json"}
            )
        if "ambry" in url:
            return httpx.Response(200, text="")
        if "voyagerJobsDashOnsiteApplyApplication" in url:
            return httpx.Response(
                200, text=apply_success, headers={"content-type": "application/json"}
            )
        raise AssertionError(f"unexpected {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=profile,
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "submitted"


def test_apply_hosted_live_resume_upload_error() -> None:
    form = load_fixture("linkedin_easy_apply_form_with_resume.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=load_fixture("linkedin_job_easy_apply.html"))
        if "voyager/api/graphql" in url:
            return httpx.Response(200, text=form, headers={"content-type": "application/json"})
        if "voyagerMediaUploadMetadata" in url:
            # Missing upload URL -> upload_easy_apply_resume raises ValueError.
            return httpx.Response(
                200, json={"value": {}}, headers={"content-type": "application/json"}
            )
        raise AssertionError(f"unexpected {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(),
            resume_file=_resume(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "resume upload failed" in (result.error or "")


def test_apply_hosted_live_submit_http_error() -> None:
    # Simple form (no file upload). Submit endpoint raises HTTP error.
    form = load_fixture("linkedin_easy_apply_form_simple.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=load_fixture("linkedin_job_easy_apply.html"))
        if "voyager/api/graphql" in url:
            return httpx.Response(200, text=form, headers={"content-type": "application/json"})
        if "voyagerJobsDashOnsiteApplyApplication" in url:
            return httpx.Response(500, text="boom")
        raise AssertionError(f"unexpected {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"


def test_apply_hosted_live_upload_but_no_file_field() -> None:
    # Resume provided + a file-upload element exists so upload runs, but the URN cannot
    # be attached because the (mutated) form has no file element in the responses map.
    # We simulate by providing a resume + a form that has a file element for the upload
    # gate but whose build_file_upload_responses returns empty (urn-less file element).
    form = {
        "data": {
            "jobsDashOnsiteApplyApplicationByJobPosting": {
                "elements": [
                    {
                        "jobApplicationForms": [
                            {
                                "questionGroupings": [
                                    {
                                        "formSection": {
                                            "formElementGroups": [
                                                {
                                                    "formElements": [
                                                        {
                                                            "required": False,
                                                            "title": {"text": "Resume"},
                                                            "formComponentResolutionResult": {
                                                                "documentUploadFormComponent": {}
                                                            },
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
    }
    import json as _json

    upload_meta = load_fixture("linkedin_media_upload_resume.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "jobs-guest/jobs/api/jobPosting" in url:
            return httpx.Response(200, text=load_fixture("linkedin_job_easy_apply.html"))
        if "voyager/api/graphql" in url:
            return httpx.Response(
                200, text=_json.dumps(form), headers={"content-type": "application/json"}
            )
        if "voyagerMediaUploadMetadata" in url:
            return httpx.Response(
                200, text=upload_meta, headers={"content-type": "application/json"}
            )
        if "ambry" in url:
            return httpx.Response(200, text="")
        raise AssertionError(f"unexpected {url}")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(),
            resume_file=_resume(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "file-upload field" in (result.error or "")


# --- _resolve_detail: parse returns None -------------------------------------


def test_resolve_detail_unparseable_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>nothing useful</body></html>")

    applier = LinkedInApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="4434410881",
            job_title="Trader",
            company="Example Co",
            job_url=EASY_APPLY_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "could not parse apply metadata" in (result.error or "")


# --- helpers -----------------------------------------------------------------


def test_detail_from_override_builds_offsite_detail() -> None:
    ctx = ApplyContext(
        job_external_id="99",
        job_title="T",
        company="C",
        job_url="https://x",
        config={},
        profile=_profile(),
    )
    detail = _detail_from_override(ctx, "https://ats/apply")
    assert detail.external_apply_url == "https://ats/apply"
    assert detail.offsite_apply is True
    assert detail.easy_apply is False


def test_extract_application_id_variants() -> None:
    assert _extract_application_id({"value": {"applicationId": 7}}) == "7"
    assert _extract_application_id({"value": {"other": 1}}) is None
    assert _extract_application_id({"id": "top"}) == "top"
    assert _extract_application_id({"value": "not-dict", "application_id": "a"}) == "a"
    assert _extract_application_id("not-a-dict") is None
    assert _extract_application_id({}) is None
