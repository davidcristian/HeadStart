"""Workday job-board apply adapter.

Workday career sites use the CXS apply flow:
  1. POST /wday/cxs/{tenant}/jobpostings/{jobPostingId}/jobapplications
  2. POST /wday/cxs/{tenant}/jobapplication/{applicationId}/name
  3. POST /wday/cxs/{tenant}/jobapplication/{applicationId}/finalize

Live submission requires an authenticated candidate session — store the
``CALYPSO_SESSION`` and ``CALYPSO_CSRF_TOKEN`` cookies (or
``session.csrf_token``) from a logged-in apply page in [site
credentials](../../docs/modules/credentials.md). Resume files are not uploaded
in v1; ``resume_text`` is sent in the preview payload comments field.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.workday_common import (
    WorkdayTarget,
    build_application_payload,
    build_name_body,
    request_headers,
    resolve_csrf_token,
    resolve_job_path,
    resolve_job_posting_id,
    resolve_target,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult
from app.schemas.profile import ProfileData
from app.scrapers.http import HttpClient


@register_applier("workday")
class WorkdayApplier(Applier):
    """Submit applications to a Workday public career site via the CXS API."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        target = resolve_target(ctx.config, ctx.job_url)
        if target is None:
            return ApplyResult(
                status="failed",
                error=(
                    "workday applier needs config.tenant + config.site "
                    "or a *.myworkdayjobs.com job URL"
                ),
            )

        job_path = resolve_job_path(ctx.config, ctx.job_url)
        if not job_path:
            return ApplyResult(
                status="failed",
                error="workday applier needs a job URL with a /job/... path or config.job_path",
            )

        job_posting_id = resolve_job_posting_id(ctx.config, ctx.job_url, ctx.job_external_id)
        if not job_posting_id:
            return ApplyResult(
                status="failed",
                error="workday applier could not determine job_posting_id from the job URL",
            )

        try:
            payload = build_application_payload(
                ctx.profile,
                job_posting_id=job_posting_id,
                job_path=job_path,
                job_title=ctx.job_title,
                company=ctx.company,
                config=ctx.config,
                cover_letter=ctx.cover_letter,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        csrf_token = resolve_csrf_token(ctx.credentials, ctx.config)
        if not csrf_token:
            return ApplyResult(
                status="failed",
                error=(
                    "workday live apply requires site credentials with CALYPSO_CSRF_TOKEN "
                    "(or session.csrf_token) from a logged-in apply page"
                ),
                payload=payload,
            )

        cookies = (ctx.credentials or {}).get("cookies") or {}
        if not cookies.get("CALYPSO_SESSION"):
            return ApplyResult(
                status="failed",
                error=(
                    "workday live apply requires site credentials with a CALYPSO_SESSION "
                    "cookie from a logged-in Workday candidate account"
                ),
                payload=payload,
            )

        http = self.http
        try:
            return self._submit_live(
                http,
                target=target,
                job_path=job_path,
                job_posting_id=job_posting_id,
                profile_payload=payload,
                profile=ctx.profile,
                config=ctx.config,
                csrf_token=csrf_token,
                credentials=ctx.credentials,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

    def _submit_live(
        self,
        http: HttpClient,
        *,
        target: WorkdayTarget,
        job_path: str,
        job_posting_id: str,
        profile_payload: dict[str, Any],
        profile: ProfileData,
        config: dict[str, Any],
        csrf_token: str,
        credentials: dict[str, dict[str, str]] | None,
    ) -> ApplyResult:
        """Create the application, submit name, and finalize."""
        create_url = f"{target.api_base()}/jobpostings/{job_posting_id}/jobapplications"
        headers = request_headers(target, job_path, csrf_token=csrf_token, credentials=credentials)
        try:
            created = http.post_json(create_url, json={}, headers=headers)
        except httpx.HTTPError as exc:
            return ApplyResult(
                status="failed",
                error=str(exc),
                payload=profile_payload,
            )

        if not isinstance(created, dict):
            return ApplyResult(
                status="failed",
                error="workday apply returned an unexpected create response",
                payload=profile_payload,
            )

        application_id = created.get("id")
        session_id = created.get("sessionId")
        if not application_id:
            message = _extract_error_message(created)
            return ApplyResult(
                status="failed",
                error=message or "workday did not create an application (sign in required?)",
                payload=profile_payload,
            )

        name_url = f"{target.api_base()}/jobapplication/{application_id}/name"
        name_headers = request_headers(
            target,
            job_path,
            csrf_token=csrf_token,
            session_id=str(session_id or ""),
            credentials=credentials,
        )
        try:
            http.post_json(
                name_url,
                json=build_name_body(profile, config),
                headers=name_headers,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(
                status="failed",
                error=str(exc),
                payload=profile_payload,
                external_application_id=str(application_id),
            )

        finalize_url = f"{target.api_base()}/jobapplication/{application_id}/finalize"
        finalize_headers = request_headers(
            target,
            job_path,
            csrf_token=csrf_token,
            session_id=str(session_id or ""),
            credentials=credentials,
        )
        try:
            finalized = http.post_json(finalize_url, json={}, headers=finalize_headers)
        except httpx.HTTPError as exc:
            return ApplyResult(
                status="failed",
                error=str(exc),
                payload=profile_payload,
                external_application_id=str(application_id),
            )

        if isinstance(finalized, dict) and finalized.get("errorCode"):
            return ApplyResult(
                status="failed",
                error=_extract_error_message(finalized) or "workday finalize rejected",
                payload=profile_payload,
                external_application_id=str(application_id),
            )

        return ApplyResult(
            status="submitted",
            payload=profile_payload,
            external_application_id=str(application_id),
        )


def _extract_error_message(response: dict[str, Any]) -> str | None:
    message = response.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    error_code = response.get("errorCode")
    if error_code:
        return str(error_code)
    return None
