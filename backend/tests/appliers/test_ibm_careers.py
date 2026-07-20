"""Tests for the IBM Careers (Avature) apply adapter."""

from __future__ import annotations

import csv
import io

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.ibm_careers import IbmCareersApplier
from app.appliers.adapters.ibm_careers_common import (
    application_methods_url,
    extract_error_message,
    extract_import_code,
    job_detail_url,
    resolve_api_key,
    resolve_careers_base_url,
    resolve_import_url,
    resolve_job_id,
)
from app.appliers.adapters.ibm_careers_payload import (
    DEFAULT_CSV_COLUMNS,
    build_candidate_row,
    build_csv_bytes,
    build_dry_run_payload,
    csv_columns,
)
from app.appliers.base import get_applier, has_applier
from app.schemas.profile import ProfileData, ProfileLinks, ResumeFile
from tests.conftest import load_json_fixture, make_http_client

_JOB_ID = "116932"
_IMPORT_URL = "https://ibmglobal.avature.net/ImportService/q9tTSBpKjiU1ejMTHaISY2dyd0gfQAYZ/"


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


def _handler(*, fail: bool = False, missing_result: bool = False) -> dict[str, object]:
    success = load_json_fixture("ibm_careers_import_accepted.json")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        host = (request.headers.get("host") or request.url.host or "").lower()
        path = request.url.path.lower()
        if "importservice" in path and request.method == "POST":
            if fail:
                return httpx.Response(
                    200,
                    json={
                        "result": "error",
                        "error": "Upload file name must end in .csv and be a CSV file",
                        "retryLater": False,
                    },
                )
            if missing_result:
                return httpx.Response(200, json={"importCode": 7})
            assert request.headers.get("X-Avature-Key") == "test-avature-key"
            return httpx.Response(200, json=success)
        return httpx.Response(404, text=f"not found: {request.method} {host}{path}")

    return {"handler": handler, "calls": calls}


def _ctx(
    *,
    dry_run: bool = True,
    import_url: str | None = _IMPORT_URL,
    with_resume: bool = True,
    job_external_id: str = _JOB_ID,
    job_url: str = f"https://careers.ibm.com/careers/JobDetail?jobId={_JOB_ID}",
    config: dict | None = None,
    credentials: dict | None = None,
) -> ApplyContext:
    profile, resume = _profile(with_resume=with_resume)
    cfg: dict = dict(config or {})
    if import_url is not None:
        cfg.setdefault("avature_import_url", import_url)
    creds = credentials
    if creds is None and not dry_run:
        creds = {"session": {"api_key": "test-avature-key"}}
    return ApplyContext(
        job_external_id=job_external_id,
        job_title="Field CTO HashiCorp",
        company="HashiCorp",
        job_url=job_url,
        config=cfg,
        profile=profile,
        resume_file=resume,
        credentials=creds,
        dry_run=dry_run,
    )


def test_has_applier_registers_ibm_careers() -> None:
    assert has_applier("ibm_careers")
    assert get_applier("ibm_careers").__class__.__name__ == "IbmCareersApplier"


def test_resolve_job_id_from_url_and_config() -> None:
    assert resolve_job_id({}, "", f"https://careers.ibm.com/careers/JobDetail?jobId={_JOB_ID}") == (
        _JOB_ID
    )
    assert (
        resolve_job_id({}, "", "https://ally.avature.net/careers/JobDetail/Slug-Title/16893")
        == "16893"
    )
    assert resolve_job_id({"job_id": "999"}, "1", "") == "999"
    assert resolve_job_id({}, "abc", "") is None


def test_resolve_careers_base_and_urls() -> None:
    assert resolve_careers_base_url({}, "") == "https://careers.ibm.com"
    assert (
        resolve_careers_base_url({}, "https://ibmglobal.avature.net/careers/JobDetail?jobId=1")
        == "https://ibmglobal.avature.net"
    )
    assert job_detail_url("https://careers.ibm.com", _JOB_ID).endswith(f"jobId={_JOB_ID}")
    assert "ApplicationMethods" in application_methods_url("https://careers.ibm.com", _JOB_ID)


def test_resolve_import_url_and_api_key() -> None:
    assert resolve_import_url({"avature_import_url": _IMPORT_URL}, None) == _IMPORT_URL
    assert resolve_import_url({}, {"session": {"import_url": _IMPORT_URL}}) == _IMPORT_URL
    assert resolve_import_url({"import_url": "https://evil.example/not-import"}, None) is None
    assert resolve_api_key({"session": {"avature_api_key": "k"}}, {}) == "k"
    assert resolve_api_key(None, {"api_key": "from-config"}) == "from-config"


def test_build_candidate_row_and_csv() -> None:
    profile, resume = _profile()
    row = build_candidate_row(profile, job_id=_JOB_ID, cover_letter="Hi", resume_file=resume)
    assert row["first_name"] == "Ada"
    assert row["last_name"] == "Lovelace"
    assert row["job_id"] == _JOB_ID
    assert row["resume_filename"] == "ada.pdf"
    assert row["resume_base64"]

    raw = build_csv_bytes(row, columns=list(DEFAULT_CSV_COLUMNS), include_header=True)
    reader = csv.reader(io.StringIO(raw.decode()))
    header = next(reader)
    values = next(reader)
    assert header[0] == "first_name"
    assert values[0] == "Ada"


def test_csv_columns_from_config() -> None:
    assert csv_columns({"import_csv_columns": "email,job_id"}) == ["email", "job_id"]
    assert csv_columns({"import_csv_columns": ["a", "b"]}) == ["a", "b"]
    assert csv_columns({}) == list(DEFAULT_CSV_COLUMNS)


def test_dry_run_without_import_url_documents_blocker() -> None:
    state = _handler()
    applier = IbmCareersApplier(http=make_http_client(state["handler"]))
    result = applier.apply(_ctx(dry_run=True, import_url=None))
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["ibm_careers_route"] == "portal_blocked"
    assert "AWS WAF" in (result.payload.get("blocker") or "")
    assert result.payload["candidate"]["resume_base64"] == "<omitted>"
    assert state["calls"] == []


def test_dry_run_with_import_url_previews_route() -> None:
    state = _handler()
    applier = IbmCareersApplier(http=make_http_client(state["handler"]))
    result = applier.apply(_ctx(dry_run=True))
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["ibm_careers_route"] == "avature_import"
    assert result.payload["blocker"] is None
    assert state["calls"] == []


def test_live_without_import_url_fails() -> None:
    state = _handler()
    applier = IbmCareersApplier(http=make_http_client(state["handler"]))
    result = applier.apply(_ctx(dry_run=False, import_url=None))
    assert result.status == "failed"
    assert result.error is not None
    assert "avature_import_url" in result.error
    assert state["calls"] == []


def test_live_submit_posts_csv_to_import_service() -> None:
    state = _handler()
    applier = IbmCareersApplier(http=make_http_client(state["handler"]))
    result = applier.apply(
        _ctx(
            dry_run=False,
            config={"import_csv_header": True, "import_return_url": "https://example.com/cb"},
        )
    )
    assert result.status == "submitted"
    assert result.external_application_id == "42"
    assert len(state["calls"]) == 1
    req = state["calls"][0]
    assert req.method == "POST"
    assert "ImportService" in str(req.url)
    body = req.read().decode("latin-1", errors="ignore")
    assert "candidates.csv" in body
    assert "Ada" in body
    assert "returnUrl" in body


def test_live_submit_import_error_response() -> None:
    state = _handler(fail=True)
    applier = IbmCareersApplier(http=make_http_client(state["handler"]))
    result = applier.apply(_ctx(dry_run=False))
    assert result.status == "failed"
    assert result.error is not None
    assert "csv" in result.error.lower()


def test_live_submit_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    applier = IbmCareersApplier(http=make_http_client(handler))
    result = applier.apply(_ctx(dry_run=False))
    assert result.status == "failed"
    assert result.error is not None


def test_live_submit_accepts_import_code_without_result() -> None:
    state = _handler(missing_result=True)
    applier = IbmCareersApplier(http=make_http_client(state["handler"]))
    result = applier.apply(_ctx(dry_run=False))
    assert result.status == "submitted"
    assert result.external_application_id == "7"


def test_missing_job_id_fails() -> None:
    applier = IbmCareersApplier(http=make_http_client(lambda _: httpx.Response(200)))
    result = applier.apply(_ctx(dry_run=True, job_external_id="", job_url="", import_url=None))
    assert result.status == "failed"
    assert "job id" in (result.error or "")


def test_profile_validation_errors() -> None:
    profile = ProfileData(full_name="Ada", email="")
    try:
        build_candidate_row(profile, job_id=_JOB_ID)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "full_name" in str(exc) or "email" in str(exc)

    applier = IbmCareersApplier(http=make_http_client(lambda _: httpx.Response(200)))
    ctx = _ctx(dry_run=True, import_url=None)
    ctx.profile = ProfileData(full_name="Ada", email="")
    result = applier.apply(ctx)
    assert result.status == "failed"


def test_extract_helpers() -> None:
    assert extract_import_code({"importCode": 9}) == "9"
    assert extract_import_code("nope") is None
    assert "must end" in extract_error_message({"error": "Upload file name must end in .csv"})
    assert extract_error_message("plain") == "plain"
    assert extract_error_message({}) == "ibm_careers apply failed"


def test_build_dry_run_payload_omits_resume_bytes() -> None:
    profile, resume = _profile()
    row = build_candidate_row(profile, job_id=_JOB_ID, resume_file=resume)
    payload = build_dry_run_payload(
        row=row,
        columns=list(DEFAULT_CSV_COLUMNS),
        job_id=_JOB_ID,
        careers_base_url="https://careers.ibm.com",
        job_detail_url=job_detail_url("https://careers.ibm.com", _JOB_ID),
        application_methods_url=application_methods_url("https://careers.ibm.com", _JOB_ID),
        import_url=None,
        resume_file=resume,
    )
    assert payload["candidate"]["resume_base64"] == "<omitted>"
    assert "resume" in payload


def test_resolve_job_id_falls_through_non_numeric_path() -> None:
    assert resolve_job_id({}, "", "https://careers.ibm.com/careers/JobDetail") is None
    assert resolve_job_id({}, "116932", "") == "116932"
    assert resolve_job_id({"jobId": "55"}, "", "") == "55"
    assert resolve_job_id({}, "", "https://careers.ibm.com/x?job_id=77") == "77"


def test_resolve_careers_base_url_variants() -> None:
    assert (
        resolve_careers_base_url({"careers_base_url": "https://custom.example/"}, "")
        == "https://custom.example"
    )
    assert (
        resolve_careers_base_url({}, "https://www.ibm.com/careers/search")
        == "https://www.ibm.com"
    )
    assert resolve_careers_base_url({}, "ftp://careers.ibm.com/x") == "https://careers.ibm.com"
    assert resolve_careers_base_url({}, "https://example.com/jobs/1") == "https://careers.ibm.com"


def test_resolve_api_key_none_and_import_url_bad_scheme() -> None:
    assert resolve_api_key(None, {}) is None
    assert resolve_import_url({"import_url": "ftp://x/ImportService/abc/"}, None) is None
    assert resolve_import_url({"import_service_url": _IMPORT_URL}, None) == _IMPORT_URL


def test_extract_error_and_import_code_branches() -> None:
    assert extract_error_message({"error": "null", "result": "rejected"}) == "rejected"
    assert extract_error_message({"error": "   "}) == "ibm_careers apply failed"
    assert extract_error_message("") == "ibm_careers apply failed"
    assert extract_import_code({"import_code": "  "}) is None
    assert extract_import_code({"importerProcessId": 3}) == "3"
    assert extract_import_code({"importCode": None, "import_code": None}) is None


def test_csv_columns_empty_fallthrough_and_email_required() -> None:
    assert csv_columns({"import_csv_columns": "  ,  "}) == list(DEFAULT_CSV_COLUMNS)
    assert csv_columns({"import_csv_columns": ["", "  "]}) == list(DEFAULT_CSV_COLUMNS)
    profile = ProfileData(full_name="Ada Lovelace", email="")
    try:
        build_candidate_row(profile, job_id=_JOB_ID)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "email" in str(exc)


def test_build_candidate_row_without_resume_and_dry_run_no_base64() -> None:
    profile, _ = _profile(with_resume=False)
    row = build_candidate_row(profile, job_id=_JOB_ID, cover_letter=None)
    assert row["resume_base64"] == ""
    payload = build_dry_run_payload(
        row=row,
        columns=["email"],
        job_id=_JOB_ID,
        careers_base_url="https://careers.ibm.com",
        job_detail_url="https://careers.ibm.com/x",
        application_methods_url="https://careers.ibm.com/y",
        import_url=_IMPORT_URL,
        resume_file=None,
    )
    assert "resume_base64" not in payload["candidate"]
    assert "resume" not in payload


def test_live_submit_without_api_key() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers.get("X-Avature-Key") is None
        return httpx.Response(200, json=load_json_fixture("ibm_careers_import_accepted.json"))

    applier = IbmCareersApplier(http=make_http_client(handler))
    result = applier.apply(_ctx(dry_run=False, credentials={"session": {}}))
    assert result.status == "submitted"
    assert len(calls) == 1


def test_import_accepted_and_safe_response_helpers() -> None:
    from app.appliers.adapters.ibm_careers import _import_accepted, _safe_response

    assert _import_accepted("not-json") is False
    assert _import_accepted({"result": "accepted"}) is True
    assert _import_accepted({"result": "error"}) is False
    assert _import_accepted({"importCode": 1, "error": "x"}) is False
    assert _safe_response({"upload": "x", "result": "ok"}) == {"result": "ok"}
    assert _safe_response("abc" * 1000).startswith("abc")
    assert _safe_response(123) == 123
