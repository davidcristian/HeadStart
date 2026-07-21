"""Tests for the Workable public careers apply adapter."""

from __future__ import annotations

import httpx
import pytest

from app.appliers import ApplyContext
from app.appliers.adapters.workable import WorkableApplier
from app.appliers.adapters.workable_common import (
    resolve_account,
    resolve_shortcode,
    turnstile_headers,
    turnstile_token,
)
from app.appliers.adapters.workable_payload import (
    build_candidate,
    extract_application_id,
    extract_error_message,
    missing_required_fields,
    required_field_ids,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import (
    EducationEntry,
    ProfileData,
    ProfileLinks,
    ResumeFile,
    WorkExperienceEntry,
)
from tests.conftest import load_json_fixture, make_http_client

_SHORTCODE = "97904BAC90"


def _profile(*, with_resume: bool = True) -> tuple[ProfileData, ResumeFile | None]:
    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        links=ProfileLinks(
            linkedin="linkedin.com/in/ada",
            github="https://github.com/ada",
            website="https://ada.example",
        ),
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        work_experience=[
            WorkExperienceEntry(
                job_title="Engineer",
                company="Analytical Engine Co",
                is_current=True,
                start_year=2020,
                start_month=1,
            )
        ],
        education=[
            EducationEntry(school="University of London", degree="BSc", field_of_study="Math")
        ],
        answers={"QA_11843967": "yes", "CA_10627": "2 weeks"},
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
    form = load_json_fixture("workable_form.json")
    upload = load_json_fixture("workable_upload.json")
    success = load_json_fixture("workable_apply_success.json")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith(f"/jobs/{_SHORTCODE}/form") and request.method == "GET":
            return httpx.Response(200, json=form)
        if path.endswith(f"/jobs/{_SHORTCODE}/form/upload/resume") and request.method == "GET":
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith(f"/jobs/{_SHORTCODE}/apply") and request.method == "POST":
            assert request.headers.get("x-turnstile-token") == "turnstile-token"
            return httpx.Response(200, json=success)
        return httpx.Response(404, text=f"not found: {request.method} {host}{path}")

    return {
        "handler": handler,
        "calls": calls,
        "form": form,
        "upload": upload,
        "success": success,
    }


def test_has_applier_registers_workable() -> None:
    assert has_applier("workable")
    assert get_applier("workable").__class__.__name__ == "WorkableApplier"


def test_resolve_shortcode_and_account_from_config_and_url() -> None:
    assert resolve_shortcode({"shortcode": _SHORTCODE}, "", "") == _SHORTCODE
    assert resolve_shortcode({}, _SHORTCODE, "") == _SHORTCODE
    assert resolve_shortcode({}, "", f"https://apply.workable.com/j/{_SHORTCODE}") == _SHORTCODE
    assert (
        resolve_shortcode({}, "", f"https://apply.workable.com/huggingface/j/{_SHORTCODE}/apply")
        == _SHORTCODE
    )
    assert resolve_shortcode({}, "not-a-shortcode", "https://example.com/jobs/1") is None
    assert resolve_account({"account": "huggingface"}, "") == "huggingface"
    assert (
        resolve_account({}, f"https://apply.workable.com/huggingface/j/{_SHORTCODE}")
        == "huggingface"
    )
    assert resolve_account({}, f"https://apply.workable.com/j/{_SHORTCODE}") is None


def test_turnstile_token_and_headers() -> None:
    assert turnstile_token({"session": {"cf_turnstile_token": "abc"}}, {}) == "abc"
    assert turnstile_token({"session": {"turnstile_token": "def"}}, {}) == "def"
    assert turnstile_token(None, {"cf_turnstile_token": "ghi"}) == "ghi"
    assert turnstile_token(None, {}) is None
    assert turnstile_headers("tok") == {"X-TURNSTILE-TOKEN": "tok"}


def test_payload_helpers_map_profile_and_required_fields() -> None:
    form = load_json_fixture("workable_form.json")
    assert isinstance(form, list)
    profile, resume = _profile()
    candidate = build_candidate(
        profile,
        config={},
        cover_letter="Hello",
        resume_file=resume,
        form=form,
    )
    assert candidate["firstname"] == "Ada"
    assert candidate["lastname"] == "Lovelace"
    assert candidate["cover_letter"] == "Hello"
    assert candidate["resume"]["name"] == "ada.pdf"
    assert candidate["experience_entries"][0]["company"] == "Analytical Engine Co"
    assert candidate["education_entries"][0]["school"] == "University of London"

    answers = {item["question_key"]: item for item in candidate["answers"]}
    assert answers["CA_47143"]["body"] == "https://github.com/ada"
    assert answers["CA_47383"]["body"] == "https://linkedin.com/in/ada"
    assert answers["QA_11843967"]["checked"] is True
    assert answers["CA_10627"]["body"] == "two_weeks"
    assert answers["gdpr"]["checked"] is True

    required = required_field_ids(form)
    assert "resume" in required
    assert "firstname" in required
    assert missing_required_fields(candidate, required, live=False) == []
    assert "resume" in missing_required_fields(candidate, required, live=True)
    assert extract_application_id({"id": "app-1"}) == "app-1"
    assert extract_error_message({"error": "Precondition Failed"}) == "Precondition Failed"


def test_dry_run_previews_candidate_without_posting() -> None:
    state = _handler()
    http = make_http_client(state["handler"])  # type: ignore[arg-type]
    profile, resume = _profile()
    applier = WorkableApplier(http=http)
    result = applier.apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Advocate Engineer",
            company="Hugging Face",
            job_url=f"https://apply.workable.com/huggingface/j/{_SHORTCODE}",
            config={"account": "huggingface"},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["shortcode"] == _SHORTCODE
    assert result.payload["account"] == "huggingface"
    assert result.payload["candidate"]["firstname"] == "Ada"
    assert not any(call.url.path.endswith("/apply") for call in state["calls"])  # type: ignore[union-attr]


def test_dry_run_fails_when_required_profile_fields_missing() -> None:
    state = _handler()
    http = make_http_client(state["handler"])  # type: ignore[arg-type]
    profile = ProfileData(full_name="Ada", email="")
    applier = WorkableApplier(http=http)
    result = applier.apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Advocate Engineer",
            company="Hugging Face",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "missing required Workable fields" in result.error


def test_live_submit_requires_turnstile_token() -> None:
    state = _handler()
    http = make_http_client(state["handler"])  # type: ignore[arg-type]
    profile, resume = _profile()
    applier = WorkableApplier(http=http)
    result = applier.apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Advocate Engineer",
            company="Hugging Face",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            resume_file=resume,
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "Turnstile" in result.error


def test_live_submit_uploads_resume_and_posts_candidate() -> None:
    state = _handler()
    http = make_http_client(state["handler"])  # type: ignore[arg-type]
    profile, resume = _profile()
    applier = WorkableApplier(http=http)
    result = applier.apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Advocate Engineer",
            company="Hugging Face",
            job_url=f"https://apply.workable.com/huggingface/j/{_SHORTCODE}",
            config={"account": "huggingface"},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "cand-fixture-001"
    assert result.payload is not None
    candidate = result.payload["candidate"]
    assert candidate["resume"].startswith("https://workable-application-form.s3")
    methods_paths = [(call.method, call.url.path) for call in state["calls"]]  # type: ignore[union-attr]
    assert ("GET", f"/api/v1/jobs/{_SHORTCODE}/form") in methods_paths
    assert ("GET", f"/api/v1/jobs/{_SHORTCODE}/form/upload/resume") in methods_paths
    assert ("POST", f"/api/v1/jobs/{_SHORTCODE}/apply") in methods_paths
    assert any(call.method == "POST" and "s3" in (call.url.host or "") for call in state["calls"])  # type: ignore[union-attr]


def test_live_submit_requires_resume_file_when_form_requires_it() -> None:
    state = _handler()
    http = make_http_client(state["handler"])  # type: ignore[arg-type]
    profile, _ = _profile(with_resume=False)
    # Still provide github/linkedin via links for other required fields.
    applier = WorkableApplier(http=http)
    result = applier.apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Advocate Engineer",
            company="Hugging Face",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "resume file" in result.error


def test_live_submit_maps_http_errors() -> None:
    form = load_json_fixture("workable_form.json")
    upload = load_json_fixture("workable_upload.json")

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith("/form") and request.method == "GET":
            return httpx.Response(200, json=form)
        if path.endswith("/form/upload/resume") and request.method == "GET":
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith("/apply"):
            return httpx.Response(409, json={"error": "turnstile rejected"})
        return httpx.Response(404)

    http = make_http_client(handler)
    profile, resume = _profile()
    applier = WorkableApplier(http=http)
    result = applier.apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Advocate Engineer",
            company="Hugging Face",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "Turnstile" in result.error


def test_missing_shortcode_fails() -> None:
    applier = WorkableApplier(http=make_http_client(lambda _r: httpx.Response(404)))
    profile, resume = _profile()
    result = applier.apply(
        ApplyContext(
            job_external_id="",
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
    assert "shortcode" in result.error


def test_form_fetch_errors_are_tolerated_on_dry_run() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/form"):
            return httpx.Response(500, text="boom")
        return httpx.Response(404)

    http = make_http_client(handler)
    profile, resume = _profile()
    # Without form schema, required list is empty so dry-run succeeds with preview.
    result = WorkableApplier(http=http).apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Role",
            company="Acme",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            resume_file=resume,
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert "form" not in result.payload


def test_form_non_list_payload_ignored() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/form"):
            return httpx.Response(200, json={"not": "a list"})
        return httpx.Response(404)

    result = WorkableApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Role",
            company="Acme",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=_profile()[0],
            resume_file=_profile()[1],
            dry_run=True,
        )
    )
    assert result.status == "dry_run"


def test_live_submit_upload_failure() -> None:
    form = load_json_fixture("workable_form.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/form") and request.method == "GET":
            return httpx.Response(200, json=form)
        if request.url.path.endswith("/form/upload/resume"):
            return httpx.Response(503, text="unavailable")
        return httpx.Response(404)

    profile, resume = _profile()
    result = WorkableApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Role",
            company="Acme",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "tok"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "presign" in result.error


def test_live_submit_empty_resume_url_fails_required_check(monkeypatch: pytest.MonkeyPatch) -> None:
    form = load_json_fixture("workable_form.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/form"):
            return httpx.Response(200, json=form)
        return httpx.Response(404)

    monkeypatch.setattr(
        "app.appliers.adapters.workable.upload_resume",
        lambda *_a, **_k: "",
    )
    profile, resume = _profile()
    result = WorkableApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Role",
            company="Acme",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "tok"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "missing required Workable fields" in result.error


def test_live_submit_response_error_payload() -> None:
    form = load_json_fixture("workable_form.json")
    upload = load_json_fixture("workable_upload.json")

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith("/form") and request.method == "GET":
            return httpx.Response(200, json=form)
        if path.endswith("/form/upload/resume"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith("/apply"):
            return httpx.Response(200, json={"error": "duplicate application"})
        return httpx.Response(404)

    profile, resume = _profile()
    result = WorkableApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Role",
            company="Acme",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error == "duplicate application"


def test_live_submit_maps_412_precondition() -> None:
    form = load_json_fixture("workable_form.json")
    upload = load_json_fixture("workable_upload.json")

    def handler(request: httpx.Request) -> httpx.Response:
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path
        if path.endswith("/form") and request.method == "GET":
            return httpx.Response(200, json=form)
        if path.endswith("/form/upload/resume"):
            return httpx.Response(200, json=upload)
        if request.method == "POST" and "s3" in host:
            return httpx.Response(204)
        if path.endswith("/apply"):
            return httpx.Response(412, text="Precondition Failed")
        return httpx.Response(404)

    profile, resume = _profile()
    result = WorkableApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Role",
            company="Acme",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            resume_file=resume,
            credentials={"session": {"cf_turnstile_token": "turnstile-token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert result.error is not None
    assert "precondition failed" in result.error


def test_live_submit_without_resume_when_not_required() -> None:
    form = [
        {
            "name": "Personal",
            "fields": [
                {"id": "firstname", "required": True, "label": "First name", "type": "text"},
                {"id": "lastname", "required": True, "label": "Last name", "type": "text"},
                {"id": "email", "required": True, "label": "Email", "type": "email"},
            ],
        }
    ]
    success = load_json_fixture("workable_apply_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/form"):
            return httpx.Response(200, json=form)
        if request.url.path.endswith("/apply"):
            assert request.headers.get("x-turnstile-token") == "tok"
            return httpx.Response(200, json=success)
        return httpx.Response(404)

    profile, _ = _profile(with_resume=False)
    result = WorkableApplier(http=make_http_client(handler)).apply(
        ApplyContext(
            job_external_id=_SHORTCODE,
            job_title="Role",
            company="Acme",
            job_url=f"https://apply.workable.com/j/{_SHORTCODE}",
            config={},
            profile=profile,
            credentials={"session": {"cf_turnstile_token": "tok"}},
            dry_run=False,
        )
    )
    assert result.status == "submitted"


def test_payload_and_resume_helper_edge_cases() -> None:
    from app.appliers.adapters.workable import _http_error_message, _response_has_error
    from app.appliers.adapters.workable_payload import (
        build_candidate,
        extract_application_id,
        extract_error_message,
        iter_form_fields,
        missing_required_fields,
    )
    from app.appliers.adapters.workable_resume import _upload_payload, upload_resume

    assert iter_form_fields(None) == []
    assert iter_form_fields(["bad", {"name": "x"}, {"fields": [None, "bad", {"id": "ok"}]}]) == [
        {"id": "ok"}
    ]
    assert required_field_ids([{"fields": [{"id": "", "required": True}]}]) == []
    assert extract_application_id("x") is None
    assert extract_application_id({"candidate": {"candidateId": "c1"}}) == "c1"
    assert extract_application_id({"candidate": {"name": "no-id"}}) is None
    assert extract_application_id({"candidate": "not-a-dict"}) is None
    assert extract_application_id({"application_id": "  "}) is None
    assert extract_application_id({"applicationId": "app-9"}) == "app-9"
    assert extract_error_message(["a", "b"]) == "workable apply failed"
    assert extract_error_message({"error": ["one", "two"]}) == "one; two"
    assert extract_error_message({"errors": {"email": "invalid"}}) == "email: invalid"
    assert extract_error_message({"errors": ["bad"]}) == "bad"
    assert extract_error_message({"errors": {}}) == "workable apply failed"
    assert extract_error_message({"message": "nope"}) == "nope"
    assert missing_required_fields({}, ["resume"], live=False) == ["resume"]
    assert missing_required_fields({"answers": [{"question_key": "x"}]}, ["x"], live=False) == ["x"]

    bare = build_candidate(
        ProfileData(full_name="Ada Lovelace", email="ada@example.com"),
        config={},
        cover_letter=None,
        resume_file=None,
        form=None,
    )
    assert "answers" not in bare

    profile = ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        answers={"headline": "Math", "website": "ada.example"},
        resume_text="Summary text",
    )
    candidate = build_candidate(
        profile,
        config={"summary": "", "CA_CFG": "from-config"},
        cover_letter=None,
        resume_file=None,
        form=[
            {
                "fields": [
                    {"id": "CA_PORT", "required": False, "label": "Portfolio site", "type": "text"},
                    {"id": "CA_DATE", "required": False, "label": "Start", "type": "date"},
                    {"id": "CA_BOOL", "required": False, "label": "Ok?", "type": "boolean"},
                    {
                        "id": "CA_DROP",
                        "required": False,
                        "label": "Choice",
                        "type": "dropdown",
                        "choices": [{"id": "a", "body": "Alpha"}],
                    },
                    {"id": "CA_CFG", "required": False, "label": "Config", "type": "text"},
                    {
                        "id": "CA_DROP2",
                        "required": False,
                        "label": "Other",
                        "type": "dropdown",
                        "choices": "bad",
                    },
                    {
                        "id": "CA_DROP3",
                        "required": False,
                        "label": "Miss",
                        "type": "dropdown",
                        "choices": ["nope", {"id": "z", "body": "Zed"}],
                    },
                ]
            }
        ],
    )
    assert candidate["headline"] == "Math"
    assert candidate["summary"] == "Summary text"
    answers = {item["question_key"]: item for item in candidate["answers"]}
    assert "website" in answers
    assert answers["CA_CFG"]["body"] == "from-config"

    profile2 = ProfileData(
        full_name="Ada",
        email="ada@example.com",
        links=ProfileLinks(website="ada.example", linkedin="", github=""),
        answers={
            "CA_DATE": "2026-01-01",
            "CA_BOOL": "no",
            "CA_DROP": "Alpha",
            "CA_PORT": "x",
            "CA_DROP2": "whatever",
            "CA_DROP3": "unknown",
        },
        work_experience=[
            WorkExperienceEntry(),
            WorkExperienceEntry(
                job_title="Eng",
                company="Co",
                end_year=2021,
                end_month=6,
            ),
        ],
        education=[
            EducationEntry(),
            EducationEntry(
                school="Uni",
                degree="BSc",
                field_of_study="CS",
                start_year=2015,
                end_year=2019,
            ),
        ],
    )
    candidate2 = build_candidate(
        profile2,
        config={},
        cover_letter=None,
        resume_file=None,
        form=[
            {
                "fields": [
                    {"id": "CA_PORT", "label": "Portfolio site", "type": "text"},
                    {"id": "CA_DATE", "label": "Start", "type": "date"},
                    {"id": "CA_BOOL", "label": "Ok?", "type": "boolean"},
                    {
                        "id": "CA_DROP",
                        "label": "Choice",
                        "type": "dropdown",
                        "choices": [{"id": "a", "body": "Alpha"}],
                    },
                    {
                        "id": "CA_DROP2",
                        "label": "Other",
                        "type": "dropdown",
                        "choices": "bad",
                    },
                    {
                        "id": "CA_DROP3",
                        "label": "Miss",
                        "type": "dropdown",
                        "choices": ["nope", {"id": "z", "body": "Zed"}],
                    },
                    {"id": "linkedin", "label": "LI", "type": "text"},
                    {"id": "github", "label": "GH", "type": "text"},
                ]
            }
        ],
    )
    answers2 = {item["question_key"]: item for item in candidate2["answers"]}
    assert answers2["CA_DATE"]["date"] == "2026-01-01"
    assert answers2["CA_BOOL"]["checked"] is False
    assert answers2["CA_DROP"]["body"] == "a"
    assert answers2["CA_PORT"]["body"] == "x"
    assert answers2["CA_DROP2"]["body"] == "whatever"
    assert answers2["CA_DROP3"]["body"] == "unknown"
    assert "linkedin" not in answers2
    assert candidate2["experience_entries"][0]["end_date"] == "2021-06-01"
    assert "start_date" not in candidate2["experience_entries"][0]
    assert candidate2["education_entries"][0]["start_date"] == "2015-01-01"
    assert candidate2["education_entries"][0]["end_date"] == "2019-01-01"

    assert _response_has_error("x") is False
    assert _response_has_error({"ok": False}) is True
    assert _response_has_error({"message": "info only"}) is False
    assert _response_has_error({"errors": {"x": 1}}) is True
    assert _http_error_message(httpx.HTTPError("network down")) == "network down"

    class _BrokenResponse:
        status_code = 500

        def read(self) -> None:
            raise httpx.HTTPError("read failed")

    broken = httpx.HTTPError("wrapper")
    broken.response = _BrokenResponse()  # type: ignore[attr-defined]
    assert _http_error_message(broken) == "wrapper"

    class _PlainResponse:
        status_code = 400
        text = "plain boom"

        def read(self) -> None:
            return None

        def json(self) -> object:
            raise ValueError("not json")

    plain = httpx.HTTPError("plain")
    plain.response = _PlainResponse()  # type: ignore[attr-defined]
    assert _http_error_message(plain) == "plain boom"
    with pytest.raises(ValueError):
        _upload_payload("bad")
    with pytest.raises(ValueError):
        _upload_payload({})
    with pytest.raises(ValueError):
        _upload_payload({"uploadPostUrl": {"url": "", "fields": {}}})

    def bad_presign(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="no")

    with pytest.raises(ValueError, match="presign"):
        upload_resume(
            make_http_client(bad_presign),
            shortcode=_SHORTCODE,
            resume_file=ResumeFile(
                filename="a.pdf", content_type="application/pdf", size_bytes=1, data=b"x"
            ),
        )

    upload = load_json_fixture("workable_upload.json")

    def s3_fail(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/form/upload/resume"):
            return httpx.Response(200, json=upload)
        return httpx.Response(403, text="denied")

    with pytest.raises(ValueError, match="S3"):
        upload_resume(
            make_http_client(s3_fail),
            shortcode=_SHORTCODE,
            resume_file=ResumeFile(
                filename="a.pdf", content_type="application/pdf", size_bytes=1, data=b"x"
            ),
        )


def test_resolve_shortcode_account_edge_cases() -> None:
    assert resolve_shortcode({}, "", "") is None
    assert resolve_shortcode({}, "", "https://apply.workable.com/huggingface/") is None
    assert resolve_shortcode({}, "", "https://apply.workable.com/j/") is None
    assert resolve_account({}, "") is None
    assert resolve_account({}, "https://example.com/huggingface/j/ABC") is None
    assert resolve_account({}, "https://apply.workable.com/api/v1/widget/accounts/x") is None
    assert resolve_account({}, "https://apply.workable.com/huggingface/jobs") is None
    assert turnstile_token({"session": {"x_turnstile_token": "z"}}, {}) == "z"
