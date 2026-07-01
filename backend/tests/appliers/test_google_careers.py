"""Tests for the Google Careers apply adapter."""

import json
from urllib.parse import parse_qs, urlparse

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.google_careers import (
    GoogleCareersApplier,
    normalize_job_detail_url,
    resolve_at_token,
)
from app.appliers.adapters.google_careers_batchexecute import (
    build_f_req,
    extract_wiz_data,
    parse_batchexecute_response,
    strip_xssi,
)
from app.appliers.adapters.google_careers_detail import (
    parse_apply_link,
    parse_job_detail_page,
)
from app.appliers.adapters.google_careers_payload import (
    build_application_payload,
    build_careers_profile,
    extract_application_id,
    extract_packet_id,
)
from app.appliers.base import get_applier
from app.schemas.profile import ApplyProfile, ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client

_JOB_URL = (
    "https://www.google.com/about/careers/applications/jobs/results/"
    "72271215732892358-software-engineer-mobile-ios-google-photos"
)
_APPLY_JOB_ID = (
    "CiUAL2FckZDp1xP1dBBfwA3xwGK9CB9_GJQRg8Fgh8u-8glqUuzNEjsAvkGZm-QFSvs9DuLKahIPlfZ1NO6s_"
    "QpNJ22OKBfg3WqInPiuAesivbD1n6-cf0aCC28-dQfznIemCg%3D%3D_V2"
)


def _profile() -> ProfileData:
    return ProfileData(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="London, UK",
        resume_text="Experienced engineer.",
        cover_letter_template="Dear {company}, I am excited about {job_title}.",
        answers={"work_authorization": "Yes"},
    )


def _google_credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"SID": "sid-value", "SAPISID": "sapisid-value"},
        "headers": {},
        "session": {"at": "csrf-token-abc"},
    }


def test_parse_job_detail_page_extracts_apply_metadata() -> None:
    detail = parse_job_detail_page(load_fixture("google_careers_job_detail.html"))
    assert detail is not None
    assert detail.external_id == "72271215732892358"
    assert detail.title.startswith("Software Engineer")
    assert detail.apply_job_id.startswith("CiUAL2Fck")
    assert detail.location_code == "AU"
    assert detail.location_label == "Sydney NSW, Australia"
    assert "apply?jobId=" in detail.apply_url


def test_build_careers_profile_maps_profile_fields() -> None:
    payload = build_careers_profile(_profile())
    assert payload["firstName"] == "Ada"
    assert payload["lastName"] == "Lovelace"
    assert payload["email"] == "ada@example.com"
    assert payload["answers"]["work_authorization"] == "Yes"


def test_build_application_payload_includes_resume_metadata() -> None:
    detail = parse_job_detail_page(load_fixture("google_careers_job_detail.html"))
    assert detail is not None
    resume = ResumeFile(
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=4,
        data=b"%PDF",
    )
    profile = ApplyProfile(**_profile().model_dump(), exists=True, resume_file=resume)
    payload = build_application_payload(
        detail,
        profile,
        job_title=detail.title,
        company="Google",
        resume_file=resume,
        include_rpc_steps=True,
    )
    assert payload["apply_job_id"] == detail.apply_job_id
    assert payload["resume_file"]["filename"] == "resume.pdf"
    assert payload["rpc_steps"][0]["rpc_id"] == "qvYBjf"
    assert "cover_letter" in payload


def test_dry_run_fetches_job_detail_and_returns_payload() -> None:
    job_html = load_fixture("google_careers_job_detail.html")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(
            "https://www.google.com/about/careers/applications/jobs/results/"
        )
        return httpx.Response(200, text=job_html)

    applier = get_applier("google_careers", http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "dry_run"
    assert result.payload is not None
    assert result.payload["careers_profile"]["email"] == "ada@example.com"
    assert result.error is None


def test_live_submit_calls_batchexecute_sequence() -> None:
    job_html = load_fixture("google_careers_job_detail.html")
    apply_html = load_fixture("google_careers_apply_page.html")
    seen_rpc: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/jobs/results/" in url:
            return httpx.Response(200, text=job_html)
        if "/applications/apply" in url and "batchexecute" not in url:
            return httpx.Response(200, text=apply_html)
        if "batchexecute" in url:
            params = parse_qs(urlparse(url).query)
            rpc_id = params["rpcids"][0]
            seen_rpc.append(rpc_id)
            if rpc_id == "qvYBjf":
                body = load_fixture("google_careers_batchexecute_save_profile.txt")
            elif rpc_id == "tBY1Qe":
                body = load_fixture("google_careers_batchexecute_create_packet.txt")
            elif rpc_id == "o6YK3":
                body = load_fixture("google_careers_batchexecute_save_packet.txt")
            elif rpc_id == "pmtdJd":
                body = load_fixture("google_careers_batchexecute_submit_packet.txt")
            else:
                raise AssertionError(f"unexpected rpc id {rpc_id}")
            posted = dict(httpx.QueryParams(request.content.decode()))
            assert posted["at"] == "csrf-token-abc"
            assert "f.req" in posted
            return httpx.Response(200, text=body)
        raise AssertionError(f"unexpected request {request.method} {url}")

    applier = GoogleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={},
            profile=_profile(),
            credentials=_google_credentials(),
            dry_run=False,
        )
    )

    assert result.status == "submitted"
    assert seen_rpc == ["qvYBjf", "tBY1Qe", "o6YK3", "pmtdJd"]
    assert result.external_application_id == "app-987654"
    assert result.payload is not None
    assert result.payload["packet_id"] == "packet-abc123"


def test_missing_google_cookies_fails_with_helpful_error() -> None:
    applier = get_applier("google_careers", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={"apply_job_id": _APPLY_JOB_ID},
            profile=_profile(),
            credentials={"cookies": {}, "headers": {}, "session": {"at": "token"}},
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "Google account cookies" in (result.error or "")


def test_missing_at_token_fails_with_helpful_error() -> None:
    applier = get_applier("google_careers", http=make_http_client(_unexpected_request))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={"apply_job_id": _APPLY_JOB_ID},
            profile=_profile(),
            credentials=_google_credentials_without_at(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "CSRF token" in (result.error or "")


def test_batchexecute_helpers_round_trip() -> None:
    req = build_f_req("tBY1Qe", [{"jobId": "abc"}])
    envelope = json.loads(req)
    assert envelope[0][0][0] == "tBY1Qe"
    raw = load_fixture("google_careers_batchexecute_create_packet.txt")
    assert strip_xssi(raw).startswith("[")
    parsed = parse_batchexecute_response(raw)
    assert extract_packet_id(extract_rpc_payload(parsed, "tBY1Qe")) == "packet-abc123"
    submit = parse_batchexecute_response(
        load_fixture("google_careers_batchexecute_submit_packet.txt")
    )
    assert extract_application_id(extract_rpc_payload(submit, "pmtdJd")) == "app-987654"


def test_resolve_at_token_prefers_credential_session() -> None:
    assert (
        resolve_at_token(
            {"session": {"at": "cred"}, "cookies": {}, "headers": {}},
            {"at": "config"},
        )
        == "cred"
    )


def test_parse_apply_link_builds_apply_url() -> None:
    apply_job_id, location_code, apply_url = parse_apply_link(
        (
            "https://www.google.com/about/careers/applications/signin?"
            f"jobId={_APPLY_JOB_ID}&loc=AU&title=Software+Engineer"
        ),
        title="Software Engineer, Mobile",
    )
    assert apply_job_id.startswith("CiUAL2Fck")
    assert location_code == "AU"
    assert "title=Software+Engineer" in apply_url


def test_normalize_job_detail_url_builds_results_path() -> None:
    url = normalize_job_detail_url("", "72271215732892358")
    assert url.endswith("/jobs/results/72271215732892358-job")


def test_extract_wiz_data_parses_apply_page() -> None:
    wiz = extract_wiz_data(load_fixture("google_careers_apply_page.html"))
    assert wiz["cfb2h"].startswith("boq_corp-hiring")
    assert wiz["SNlM0e"] == "csrf-token-abc"


def _google_credentials_without_at() -> dict[str, dict[str, str]]:
    creds = _google_credentials()
    creds["session"] = {}
    return creds


def extract_rpc_payload(payload: object, rpc_id: str) -> object:
    assert isinstance(payload, list)
    for item in payload:
        if isinstance(item, list) and item[:2] == ["wrb.fr", rpc_id]:
            return json.loads(item[2])
    raise AssertionError(f"missing rpc {rpc_id}")


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")
