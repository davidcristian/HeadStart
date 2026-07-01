"""Google Careers apply adapter.

Google Careers has no public employer API. Applications are submitted through the
authenticated HiringCportalFrontendUi batchexecute RPC flow:

  1. SaveCareersProfile (`qvYBjf`)
  2. CreatePacket (`tBY1Qe`)
  3. SavePacket (`o6YK3`)
  4. SubmitPacket (`pmtdJd`)

Config / context:
  - `config["apply_job_id"]`: opaque apply token (optional if derivable from job URL).
  - Credential cookies: logged-in Google account session (SID, SAPISID, etc.).
  - Credential `session["at"]` or `session["csrf_token"]`: CSRF token (`SNlM0e`).

Use `dry_run=True` to preview the mapped Careers profile and apply URL without
Google authentication. Live submit is best-effort and may require additional
`profile.answers` mappings for employer-specific questions.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.google_careers_batchexecute import (
    RPC_CREATE_PACKET,
    RPC_SAVE_PACKET,
    RPC_SAVE_PROFILE,
    RPC_SUBMIT_PACKET,
    GoogleCareersRpcError,
    call_batchexecute,
    extract_wiz_data,
)
from app.appliers.adapters.google_careers_detail import (
    GoogleCareersJobDetail,
    parse_job_detail_page,
    resolve_external_id,
)
from app.appliers.adapters.google_careers_payload import (
    build_application_payload,
    build_careers_profile,
    build_create_packet_args,
    build_save_packet_args,
    build_save_profile_args,
    build_submit_packet_args,
    extract_application_id,
    extract_packet_id,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult

_APPLICATIONS_BASE = "https://www.google.com/about/careers/applications"
_APPLY_SOURCE_PATH = "/about/careers/applications/apply"


@register_applier("google_careers")
class GoogleCareersApplier(Applier):
    """Submit (or preview) applications on Google Careers."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        try:
            detail = self._resolve_detail(ctx)
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        try:
            payload = build_application_payload(
                detail,
                ctx.profile,
                job_title=ctx.job_title,
                company=ctx.company,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
                include_rpc_steps=ctx.dry_run,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        at_token = resolve_at_token(ctx.credentials, ctx.config)
        if not at_token:
            return ApplyResult(
                status="failed",
                error=(
                    "google_careers live apply requires a Google CSRF token in "
                    "credential session.at or session.csrf_token"
                ),
                payload=payload,
            )
        if not has_google_session_cookies(ctx.credentials):
            return ApplyResult(
                status="failed",
                error=(
                    "google_careers live apply requires logged-in Google account "
                    "cookies (e.g. SID and SAPISID) in site credentials"
                ),
                payload=payload,
            )

        try:
            wiz = self._load_wiz(ctx, detail)
            careers_profile = build_careers_profile(ctx.profile)
            call_batchexecute(
                self.http,
                rpc_id=RPC_SAVE_PROFILE,
                args=build_save_profile_args(careers_profile),
                wiz=wiz,
                at_token=at_token,
                source_path=_APPLY_SOURCE_PATH,
            )
            create_result = call_batchexecute(
                self.http,
                rpc_id=RPC_CREATE_PACKET,
                args=build_create_packet_args(detail),
                wiz=wiz,
                at_token=at_token,
                source_path=_APPLY_SOURCE_PATH,
                req_id=100002,
            )
            packet_id = extract_packet_id(create_result)
            if not packet_id:
                return ApplyResult(
                    status="failed",
                    error="google_careers CreatePacket did not return a packet id",
                    payload=payload,
                )

            call_batchexecute(
                self.http,
                rpc_id=RPC_SAVE_PACKET,
                args=build_save_packet_args(
                    packet_id,
                    careers_profile=careers_profile,
                    cover_letter=ctx.cover_letter,
                    job_title=ctx.job_title,
                    company=ctx.company,
                    profile=ctx.profile,
                ),
                wiz=wiz,
                at_token=at_token,
                source_path=_APPLY_SOURCE_PATH,
                req_id=100003,
            )
            submit_result = call_batchexecute(
                self.http,
                rpc_id=RPC_SUBMIT_PACKET,
                args=build_submit_packet_args(packet_id),
                wiz=wiz,
                at_token=at_token,
                source_path=_APPLY_SOURCE_PATH,
                req_id=100004,
            )
        except (httpx.HTTPError, GoogleCareersRpcError, ValueError) as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        payload["packet_id"] = packet_id
        app_id = extract_application_id(submit_result)
        return ApplyResult(
            status="submitted",
            payload=payload,
            external_application_id=app_id or packet_id,
        )

    def _resolve_detail(self, ctx: ApplyContext) -> GoogleCareersJobDetail:
        configured = str(ctx.config.get("apply_job_id") or "").strip()
        if configured:
            external_id = resolve_external_id(ctx.job_url, ctx.job_external_id)
            location_code = str(ctx.config.get("location_code") or "").strip()
            title_token = ctx.job_title.split(",")[0].strip().replace(" ", "+")
            apply_url = (
                f"{_APPLICATIONS_BASE}/apply"
                f"?jobId={configured}&loc={location_code}&title={title_token}"
            )
            return GoogleCareersJobDetail(
                external_id=external_id,
                title=ctx.job_title,
                apply_job_id=configured,
                apply_url=apply_url,
                company=ctx.company,
                company_resource=str(ctx.config.get("company_resource") or ""),
                location_code=location_code,
                location_label=str(ctx.config.get("location_label") or ""),
            )

        job_url = normalize_job_detail_url(ctx.job_url, ctx.job_external_id)
        html = self.http.get_text(job_url)
        detail = parse_job_detail_page(html)
        if detail is None:
            raise ValueError(
                "google_careers applier could not parse job detail metadata; "
                "set config.apply_job_id or use a /jobs/results/<id>-<slug> job URL"
            )
        return detail

    def _load_wiz(self, ctx: ApplyContext, detail: GoogleCareersJobDetail) -> dict[str, Any]:
        apply_html = self.http.get_text(detail.apply_url)
        return extract_wiz_data(apply_html)


def normalize_job_detail_url(job_url: str, external_id: str) -> str:
    """Return a canonical job detail URL for metadata extraction."""
    if job_url and "/jobs/results/" in job_url:
        return job_url
    listing_id = resolve_external_id(job_url, external_id)
    return f"{_APPLICATIONS_BASE}/jobs/results/{listing_id}-job"


def resolve_at_token(
    credentials: dict[str, dict[str, str]] | None, config: dict[str, Any]
) -> str | None:
    """CSRF token (`SNlM0e`) from credential session or source config."""
    if credentials:
        session = credentials.get("session") or {}
        for key in ("at", "csrf_token", "SNlM0e"):
            value = session.get(key)
            if value:
                return str(value)
    for key in ("at", "csrf_token", "SNlM0e"):
        value = config.get(key)
        if value:
            return str(value)
    return None


def has_google_session_cookies(credentials: dict[str, dict[str, str]] | None) -> bool:
    """True when credential cookies look like a Google account session."""
    if not credentials:
        return False
    cookies = credentials.get("cookies") or {}
    if not cookies:
        return False
    names = {name.lower() for name in cookies}
    return bool(names.intersection({"sid", "sapisid", "__secure-1psid", "hsid"}))
