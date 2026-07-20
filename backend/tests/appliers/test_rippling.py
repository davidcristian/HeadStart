"""Tests for the Rippling ATS apply adapter."""

from __future__ import annotations

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.rippling import RipplingApplier
from app.appliers.adapters.rippling_common import (
    resolve_board,
    resolve_job_id,
    turnstile_token,
)
from app.appliers.adapters.rippling_payload import (
    basic_questions,
    build_application_form_response,
    extract_application_id,
    extract_error_message,
    missing_required_fields,
    required_question_oids,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData, ProfileLinks, ResumeFile, WorkExperienceEntry
from tests.conftest import load_json_fixture, make_http_client

_JOB_ID = "2f0674e6-f01f-4ecd-b459-e947241c211f"


def _profile(*, with_resume: bool = True) -> tuple[ProfileData, ResumeFile | None]:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(
            linkedin="linkedin.com/in/ada",
            website="https://ada.example",
        ),
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="Analytical Engine Co",
                is_current=True,
            )
        ],
        answers={"country_code": "GB"},
    )
    resume = None
    if with_resume:
        resume = ResumeFile(
            filename="ada.pdf",
            content_type="application/pdf",
            size_bytes=12,
            data=b"%PDF-1.4 ada",
        )
    return profile, resume


def _handler() -> dict[str, object]:
    detail = load_json_fixture("rippling_job_detail.json")
    upload = load_json_fixture("rippling_file_upload_url.json")
    success = load_json_fixture("rippling_apply_success.json")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith(f"/jobs/{_JOB_ID}/apply") and request.method == "POST":
            assert request.headers.get("cf-client-response") == "turnstile-token"
            return httpx.Response(200, json=success)
        return httpx.Response(404, text=f"not found: {request.method} {host}{path}")

    return {
        "handler": handler,
        "calls": calls,
        "detail": detail,
        "upload": upload,
        "success": success,
    }


def test_has_applier_registers_rippling() -> None:
    assert has_applier("rippling")
    assert get_applier("rippling").__class__.__name__ == "RipplingApplier"


def test_resolve_board_and_job_id_from_config_and_url() -> None:
    assert resolve_board({"board": "rippling"}, "") == "rippling"
    assert resolve_board({}, f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}") == "rippling"
    assert (
        resolve_board(
            {},
            f"https://api.rippling.com/platform/api/ats/v1/board/acme/jobs/{_JOB_ID}",
        )
        == "acme"
    )
    assert resolve_board({}, "https://example.com/jobs/1") is None
    assert resolve_job_id({}, _JOB_ID, "") == _JOB_ID
    assert (
        resolve_job_id({}, "", f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}/apply") == _JOB_ID
    )
    assert resolve_job_id({}, "not-a-uuid", "") is None


def test_turnstile_token_from_session_or_config() -> None:
    assert turnstile_token({"session": {"cf_turnstile_token": "abc"}}, {}) == "abc"
    assert turnstile_token({"session": {"turnstile_token": "def"}}, {}) == "def"
    assert turnstile_token(None, {"cf_turnstile_token": "ghi"}) == "ghi"
    assert turnstile_token(None, {}) is None


def test_payload_helpers_map_profile_and_required_fields() -> None:
    detail = load_json_fixture("rippling_job_detail.json")
    assert isinstance(detail, dict)
    profile, resume = _profile()
    form = build_application_form_response(
        profile,
        config={},
        company="Rippling",
        cover_letter="Hello",
        resume_file=resume,
    )
    assert form["first_name"] == "Ada"
    assert form["last_name"] == "Lovelace"
    assert form["linkedin_link"] == "https://linkedin.com/in/ada"
    assert form["current_company"] == "Analytical Engine Co"
    assert form["location"] == "London"
    assert form["country_code"] == "GB"
    assert form["cover_letter_text"] == "Hello"
    assert form["resume_file"]["filename"] == "ada.pdf"

    required = required_question_oids(detail)
    assert "resume" in required
    assert "first_name" in required
    assert missing_required_fields(form, required, live=False) == []
    assert "resume" in missing_required_fields(form, required, live=True)
    assert extract_application_id({"applicationId": "app-1"}) == "app-1"
    assert extract_error_message({"error": "turnstile_verification_failure"}) == (
        "turnstile_verification_failure"
    )


def test_dry_run_builds_preview_payload() -> None:
    fixtures = _handler()
    profile, resume = _profile()
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    form = result.payload["applicationFormResponse"]
    assert form["email"] == "ada@example.com"
    assert form["resume_file"]["filename"] == "ada.pdf"
    assert "resume" not in form
    assert result.payload["job"]["required_questions"]


def test_dry_run_fails_when_required_resume_missing() -> None:
    fixtures = _handler()
    profile, _ = _profile(with_resume=False)
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "resume" in result.error


def test_live_apply_requires_turnstile_token() -> None:
    fixtures = _handler()
    profile, resume = _profile()
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "Turnstile" in result.error


def test_live_apply_uploads_resume_and_submits() -> None:
    fixtures = _handler()
    profile, resume = _profile()
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            cover_letter="Please consider my application.",
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "app-fixture-001"
    assert result.payload is not None
    form = result.payload["applicationFormResponse"]
    assert form["resume"].startswith("https://prod-rippling-us1-ats.s3.amazonaws.com/")
    assert "uploadsig=" in form["resume"]
    assert form["resumeFileExtension"] == "application/pdf"
    assert form["cover_letter"].startswith("https://")
    assert form["coverLetterFileExtension"] == "text/plain"

    methods = [request.method for request in fixtures["calls"]]  # type: ignore[index]
    assert methods.count("GET") >= 2  # job detail + upload url (+ cover upload url)
    assert "POST" in methods


def test_live_apply_reports_turnstile_failure() -> None:
    detail = load_json_fixture("rippling_job_detail.json")
    upload = load_json_fixture("rippling_file_upload_url.json")

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith("/apply"):
            return httpx.Response(401, json={"error": "turnstile_verification_failure"})
        return httpx.Response(404)

    profile, resume = _profile()
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Account Executive",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "bad-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "turnstile_verification_failure" in result.error


def test_missing_board_fails() -> None:
    profile, resume = _profile()
    result = RipplingApplier().apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Acme",
            job_url="https://example.com/jobs/1",
            config={},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "config.board" in result.error


def test_missing_job_id_fails() -> None:
    profile, resume = _profile()
    result = RipplingApplier().apply(
        ApplyContext(
            job_external_id="not-a-uuid",
            job_title="Role",
            company="Acme",
            job_url="https://ats.rippling.com/rippling/jobs",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "job UUID" in result.error


def test_resolve_job_id_from_query_string() -> None:
    assert (
        resolve_job_id({}, "", f"https://ats.rippling.com/rippling/jobs?jobId={_JOB_ID}") == _JOB_ID
    )
    assert resolve_board({"board": "bad board!"}, "") is None
    assert resolve_board({}, "") is None


def test_live_job_detail_http_error_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    profile, resume = _profile()
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "tok"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None


def test_dry_run_continues_when_job_detail_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    profile, resume = _profile()
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"


def test_live_apply_requires_resume_when_question_required() -> None:
    fixtures = _handler()
    profile, _ = _profile(with_resume=False)
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "resume file" in result.error


def test_live_apply_without_cover_letter() -> None:
    fixtures = _handler()
    profile, resume = _profile()
    profile.cover_letter_template = ""
    client = make_http_client(fixtures["handler"])  # type: ignore[arg-type]
    result = RipplingApplier(http=client).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert "cover_letter" not in (result.payload or {})["applicationFormResponse"]


def test_live_apply_upload_failure() -> None:
    detail = load_json_fixture("rippling_job_detail.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json={"not": "valid"})
        return httpx.Response(404)

    profile, resume = _profile()
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "file_upload_url" in result.error


def test_live_apply_reports_error_body() -> None:
    detail = load_json_fixture("rippling_job_detail.json")
    upload = load_json_fixture("rippling_file_upload_url.json")

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith("/apply"):
            return httpx.Response(200, json={"ok": False, "message": "duplicate application"})
        return httpx.Response(404)

    profile, resume = _profile()
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "duplicate application"


def test_live_apply_missing_required_after_upload() -> None:
    detail = load_json_fixture("rippling_job_detail.json")
    assert isinstance(detail, dict)
    active = dict(detail["activeJobApplication"])
    questions = list(active["basicQuestions"])
    questions.append(
        {
            "oid": "nickname",
            "fieldType": "SHORT_ANSWER",
            "title": "Nickname",
            "required": True,
        }
    )
    active["basicQuestions"] = questions
    detail = {**detail, "activeJobApplication": active}
    upload = load_json_fixture("rippling_file_upload_url.json")

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        return httpx.Response(404)

    profile, resume = _profile()
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "nickname" in result.error


def test_payload_helpers_cover_edge_branches() -> None:
    assert basic_questions(None) == []
    assert basic_questions({"activeJobApplication": None}) == []
    assert basic_questions({"activeJobApplication": {"basicQuestions": "nope"}}) == []
    assert (
        required_question_oids(
            {"activeJobApplication": {"basicQuestions": [None, {"required": True}]}}
        )
        == []
    )
    assert (
        required_question_oids(
            {"activeJobApplication": {"basicQuestions": [{"oid": "x", "required": False}]}}
        )
        == []
    )

    profile = ProfileData(
        full_name="Solo",
        email="s@example.com",
        links=ProfileLinks(linkedin="https://linkedin.com/in/solo", website=""),
        answers={
            "pronouns": "DEFAULT_THEY",
            "pronouns_custom": "xe/xem",
            "rippling_nickname": "Sol",
            "company": "From Answers",
        },
        work_experience=[WorkExperienceEntry(company="Past Co", is_current=False)],
    )
    form = build_application_form_response(
        profile,
        config={"pronoun_strategy": "CUSTOM", "timezone": "Europe/London", "jobSite": "embed"},
        company="",
        cover_letter="  ",
        resume_file=None,
        resume_url="https://example.test/r.pdf",
        resume_content_type=None,
        cover_letter_url="https://example.test/c.txt",
        cover_letter_content_type=None,
        include_resume_meta=False,
    )
    assert form["last_name"] == "Solo"
    assert form["pronounStrategy"] == "CUSTOM"
    assert form["pronounCustomValue"] == "xe/xem"
    assert form["nickname"] == "Sol"
    assert form["current_company"] == "From Answers"
    assert form["resumeFileExtension"] == "application/pdf"
    assert form["coverLetterFileExtension"] == "text/plain"
    assert form["timezone"] == "Europe/London"

    profile2 = ProfileData(
        full_name="A B",
        email="a@example.com",
        location="Remote",
        work_experience=[WorkExperienceEntry(company="Only Past", is_current=False)],
    )
    form2 = build_application_form_response(
        profile2,
        config={},
        company="Fallback Co",
        cover_letter=None,
        resume_file=None,
        include_resume_meta=True,
    )
    assert form2["current_company"] == "Only Past"
    assert form2["location"] == "Remote"
    assert "resume_file" not in form2

    form3 = build_application_form_response(
        ProfileData(full_name="Z", email="z@example.com"),
        config={},
        company="Acme",
        cover_letter=None,
        resume_file=None,
    )
    assert form3["current_company"] == "Acme"

    assert missing_required_fields({"resume": "x"}, ["resume"], live=True) == []
    assert missing_required_fields({}, ["resume"], live=True) == ["resume"]
    assert missing_required_fields({"resume_file": {"filename": "x"}}, ["resume"], live=False) == []
    assert missing_required_fields({}, ["cover_letter"], live=True) == ["cover_letter"]
    assert missing_required_fields({}, ["cover_letter"], live=False) == []
    assert missing_required_fields({"email": ""}, ["email"], live=False) == ["email"]

    assert extract_application_id("nope") is None
    assert extract_application_id({"data": {"uuid": "nested-1"}}) == "nested-1"
    assert extract_application_id({"data": {}}) is None
    assert extract_error_message({"detail": "bad"}) == "bad"
    assert extract_error_message({"error": 1}) == "rippling apply failed"
    assert extract_error_message("x") == "rippling apply failed"
    assert extract_error_message({"error": "turnstile_verification_failure"}) == (
        "turnstile_verification_failure"
    )


def test_resume_upload_helpers() -> None:
    from app.appliers.adapters import rippling_resume as resume_mod

    upload = load_json_fixture("rippling_file_upload_url.json")
    assert isinstance(upload, dict)
    with_acl = {
        "data": {
            **upload["data"],
            "acl": "public-read",
            "fields": {k: v for k, v in upload["data"]["fields"].items() if k != "uploadsig"},
            "finalUrl": {
                "url": (
                    "https://prod-rippling-us1-ats.s3.amazonaws.com/"
                    "common/ats_public/fixture-resume.pdf?uploadsig=already"
                )
            },
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=with_acl)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        return httpx.Response(404)

    url, ctype = resume_mod.upload_application_file(
        make_http_client(handler),
        board="rippling",
        content=b"hello",
        filename=None,
        content_type=None,
    )
    assert ctype == "application/octet-stream"
    assert "uploadsig=already" in url

    def bad_s3(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/utility/file_upload_url"):
            return httpx.Response(200, json=upload)
        return httpx.Response(403, text="denied")

    try:
        resume_mod.upload_application_file(
            make_http_client(bad_s3),
            board="rippling",
            resume_file=ResumeFile(
                filename="",
                content_type="  ",
                size_bytes=1,
                data=b"x",
            ),
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "S3" in str(exc)

    try:
        resume_mod.upload_application_file(make_http_client(handler), board="rippling")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "resume_file or content" in str(exc)

    try:
        resume_mod._upload_payload("nope")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        resume_mod._upload_payload({"data": []})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        resume_mod._upload_payload({"data": {"url": "", "fields": {}, "finalUrl": {}}})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        resume_mod._upload_payload(
            {"data": {"url": "https://s3.example/", "fields": {}, "finalUrl": {"url": ""}}}
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass

    bare = resume_mod._final_resume_url({"final_url": "https://s3.example/f.pdf"}, {})
    assert bare == "https://s3.example/f.pdf"


def test_live_apply_without_resume_when_not_required() -> None:
    detail = {
        "uuid": _JOB_ID,
        "name": "Role",
        "companyName": "Rippling",
        "activeJobApplication": {
            "basicQuestions": [
                {"oid": "first_name", "required": True},
                {"oid": "last_name", "required": True},
                {"oid": "email", "required": True},
            ]
        },
    }
    success = load_json_fixture("rippling_apply_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/jobs/{_JOB_ID}") and request.method == "GET":
            return httpx.Response(200, json=detail)
        if path.endswith("/apply") and request.method == "POST":
            return httpx.Response(200, json=success)
        return httpx.Response(404)

    profile, _ = _profile(with_resume=False)
    profile.cover_letter_template = ""
    result = RipplingApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_JOB_ID,
            job_title="Role",
            company="Rippling",
            job_url=f"https://ats.rippling.com/rippling/jobs/{_JOB_ID}",
            config={"board": "rippling", "current_company": "HeadStart"},
            profile=profile,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "submitted"


def test_resolve_job_id_skips_non_uuid_jobs_segment() -> None:
    assert resolve_job_id({}, "", "https://ats.rippling.com/rippling/jobs/not-uuid") is None
    assert resolve_job_id({}, "", "https://ats.rippling.com/rippling/jobs") is None
    assert resolve_job_id({}, "", "https://ats.rippling.com/rippling/openings/x") is None


def test_payload_pronoun_without_custom_and_empty_current_role() -> None:
    profile = ProfileData(
        full_name="A B",
        email="a@example.com",
        answers={"pronouns": "DEFAULT_THEY"},
        work_experience=[
            WorkExperienceEntry(company="", is_current=True),
            WorkExperienceEntry(company="Past Co", is_current=False),
        ],
    )
    form = build_application_form_response(
        profile,
        config={},
        company="",
        cover_letter=None,
        resume_file=None,
        include_resume_meta=True,
    )
    assert form["pronounStrategy"] == "DEFAULT_THEY"
    assert "pronounCustomValue" not in form
    assert form["current_company"] == "Past Co"

    empty_company = build_application_form_response(
        ProfileData(full_name="X Y", email="x@example.com"),
        config={"current_company": "   "},
        company="",
        cover_letter=None,
        resume_file=None,
    )
    assert "current_company" not in empty_company


def test_resume_uploadsig_already_present() -> None:
    from app.appliers.adapters import rippling_resume as resume_mod

    url = resume_mod._final_resume_url(
        {"final_url": "https://s3.example/f.pdf?uploadsig=keep"},
        {"uploadsig": "new"},
    )
    assert url == "https://s3.example/f.pdf?uploadsig=keep"

    from app.appliers.adapters.rippling import _http_error_message, _response_has_error

    assert _response_has_error("x") is False
    assert _response_has_error({"error_code": "MALFORMED"}) is True
    assert _response_has_error({"ok": False}) is True
    assert _response_has_error({"ok": True}) is False

    bare = httpx.RequestError("boom", request=httpx.Request("POST", "https://example.test"))
    assert "boom" in _http_error_message(bare)

    request = httpx.Request("POST", "https://example.test/apply")
    response = httpx.Response(400, json={"message": "nope"}, request=request)
    err = httpx.HTTPStatusError("bad", request=request, response=response)
    assert _http_error_message(err) == "nope"

    response2 = httpx.Response(400, content=b"not-json", request=request)
    err2 = httpx.HTTPStatusError("bad", request=request, response=response2)
    assert "bad" in _http_error_message(err2) or "400" in _http_error_message(err2)
