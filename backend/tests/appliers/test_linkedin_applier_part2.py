"""Flow-level tests for the LinkedIn applier: hosted live resume/upload/submit branches."""

from __future__ import annotations

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.linkedin import LinkedInApplier
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


# --- _apply_hosted branches --------------------------------------------------


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
