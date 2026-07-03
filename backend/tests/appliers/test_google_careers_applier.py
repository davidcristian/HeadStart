"""Flow-level tests for the Google Careers applier covering error branches."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.appliers import ApplyContext
from app.appliers.adapters.google_careers import (
    GoogleCareersApplier,
    has_google_session_cookies,
    resolve_at_token,
)
from app.schemas.profile import ProfileData, ResumeFile
from tests.conftest import load_fixture, make_http_client

_JOB_URL = (
    "https://www.google.com/about/careers/applications/jobs/results/"
    "72271215732892358-software-engineer"
)
_APPLY_JOB_ID = "APPLYTOKEN"


def _profile(**overrides: object) -> ProfileData:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+1 555 0100",
        "location": "London, UK",
        "cover_letter_template": "Dear {company}",
        "answers": {"work_authorization": "Yes"},
    }
    base.update(overrides)
    return ProfileData(**base)


def _credentials() -> dict[str, dict[str, str]]:
    return {
        "cookies": {"SID": "sid", "SAPISID": "sapisid"},
        "headers": {},
        "session": {"at": "csrf-token-abc"},
    }


def _resume() -> ResumeFile:
    return ResumeFile(
        filename="resume.pdf", content_type="application/pdf", size_bytes=4, data=b"%PDF"
    )


def _unexpected(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.method} {request.url}")


# --- resolve_at_token / has_google_session_cookies ---------------------------


def test_resolve_at_token_from_config_when_no_session() -> None:
    assert resolve_at_token(None, {"csrf_token": "cfg"}) == "cfg"
    assert resolve_at_token({"session": {}, "cookies": {}}, {"SNlM0e": "cfg2"}) == "cfg2"


def test_resolve_at_token_none_when_absent() -> None:
    assert resolve_at_token(None, {}) is None


def test_has_google_session_cookies_variants() -> None:
    assert has_google_session_cookies(None) is False
    assert has_google_session_cookies({"cookies": {}}) is False
    assert has_google_session_cookies({"cookies": {"random": "x"}}) is False
    assert has_google_session_cookies({"cookies": {"SID": "x"}}) is True


# --- apply() error branches --------------------------------------------------


def test_apply_resolve_detail_parse_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>no ds:0 here</html>")

    applier = GoogleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={},
            profile=_profile(),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "could not parse job detail" in (result.error or "")


def test_apply_build_payload_value_error() -> None:
    # Configured apply id skips network; profile with single-word name -> payload error.
    applier = GoogleCareersApplier(http=make_http_client(_unexpected))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={"apply_job_id": _APPLY_JOB_ID},
            profile=_profile(full_name="Ada"),
            dry_run=True,
        )
    )
    assert result.status == "failed"
    assert "first and last name" in (result.error or "")


def test_apply_resume_upload_error() -> None:
    job_html = load_fixture("google_careers_job_detail.html")
    apply_html = load_fixture("google_careers_apply_page.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/jobs/results/" in url:
            return httpx.Response(200, text=job_html)
        if "/applications/apply" in url and "batchexecute" not in url:
            return httpx.Response(200, text=apply_html)
        if "attachmentupload/upload" in url:
            # Start returns no session URL -> upload raises ValueError.
            return httpx.Response(200, text="")
        raise AssertionError(f"unexpected {url}")

    applier = GoogleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            resume_file=_resume(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "X-Goog-Upload-URL" in (result.error or "")


def test_apply_create_packet_no_id() -> None:
    job_html = load_fixture("google_careers_job_detail.html")
    apply_html = load_fixture("google_careers_apply_page.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/jobs/results/" in url:
            return httpx.Response(200, text=job_html)
        if "/applications/apply" in url and "batchexecute" not in url:
            return httpx.Response(200, text=apply_html)
        if "batchexecute" in url:
            rpc_id = parse_qs(urlparse(url).query)["rpcids"][0]
            if rpc_id == "qvYBjf":
                return httpx.Response(
                    200, text=load_fixture("google_careers_batchexecute_save_profile.txt")
                )
            if rpc_id == "tBY1Qe":
                # CreatePacket returns an empty list head -> no packet id.
                return httpx.Response(200, text=')]}\'\n[["wrb.fr","tBY1Qe","[]"]]')
            raise AssertionError(f"unexpected rpc {rpc_id}")
        raise AssertionError(f"unexpected {url}")

    applier = GoogleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "did not return a packet id" in (result.error or "")


def test_apply_batchexecute_rpc_error() -> None:
    job_html = load_fixture("google_careers_job_detail.html")
    apply_html = load_fixture("google_careers_apply_page.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/jobs/results/" in url:
            return httpx.Response(200, text=job_html)
        if "/applications/apply" in url and "batchexecute" not in url:
            return httpx.Response(200, text=apply_html)
        if "batchexecute" in url:
            # SaveProfile returns an error envelope -> GoogleCareersRpcError.
            return httpx.Response(
                200,
                text=')]}\'\n[["er",0,0,"fallback",0,"rpc exploded",0,1]]',
            )
        raise AssertionError(f"unexpected {url}")

    applier = GoogleCareersApplier(http=make_http_client(handler))
    result = applier.apply(
        ApplyContext(
            job_external_id="72271215732892358",
            job_title="Software Engineer",
            company="Google",
            job_url=_JOB_URL,
            config={},
            profile=_profile(),
            credentials=_credentials(),
            dry_run=False,
        )
    )
    assert result.status == "failed"
    assert "rpc exploded" in (result.error or "")
