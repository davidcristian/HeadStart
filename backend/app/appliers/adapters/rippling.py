"""Rippling ATS public job-board apply adapter.

Submits applications via the public board apply API used by
``ats.rippling.com/<board>/jobs/<uuid>/apply``:

  GET  https://api.rippling.com/platform/api/ats/v1/board/<board>/jobs/<uuid>
  GET  https://api.rippling.com/platform/api/ats/v1/utility/file_upload_url
  POST https://api.rippling.com/platform/api/ats/v1/board/<board>/jobs/<uuid>/apply

Config / context:
  - ``config["board"]``: board slug (optional when derivable from ``job_url``).
  - ``config["job_id"]`` / ``uuid``: optional job UUID override.
  - ``config["current_company"]``, ``country_code``, ``timezone``, ``job_site``.
  - Profile ``answers`` keys may fill basic-question oids (``current_company``, …).
  - Live submit requires Cloudflare Turnstile: credential
    ``session.cf_turnstile_token`` (or ``turnstile_token`` / config override).

Dry-run previews the apply JSON (and required questions) without uploading or
POSTing. Live submit uploads the resume via Rippling's presigned S3 POST, then
POSTs the apply payload with Turnstile headers.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.rippling_common import (
    apply_url,
    job_detail_url,
    resolve_board,
    resolve_job_id,
    turnstile_headers,
    turnstile_token,
)
from app.appliers.adapters.rippling_payload import (
    build_application_form_response,
    build_apply_payload,
    extract_application_id,
    extract_error_message,
    missing_required_fields,
    required_question_oids,
)
from app.appliers.adapters.rippling_resume import upload_application_file
from app.appliers.base import Applier, register_applier
from app.appliers.text import render_cover_letter
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("rippling")
class RipplingApplier(Applier):
    """Submit applications to a Rippling public ATS board."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        board = resolve_board(ctx.config, ctx.job_url)
        if not board:
            return ApplyResult(
                status="failed",
                error=(
                    "rippling applier needs config.board "
                    "or an ats.rippling.com / board API job URL"
                ),
            )

        job_id = resolve_job_id(ctx.config, ctx.job_external_id, ctx.job_url)
        if not job_id:
            return ApplyResult(
                status="failed",
                error=(
                    "rippling applier needs a job UUID in job_external_id, "
                    "config.job_id, or job_url"
                ),
            )

        job_detail: dict[str, Any] | None = None
        try:
            raw_detail = self.http.get_json(job_detail_url(board, job_id))
        except httpx.HTTPError as exc:
            if not ctx.dry_run:
                return ApplyResult(status="failed", error=str(exc))
        else:
            job_detail = raw_detail if isinstance(raw_detail, dict) else None

        cover_letter = ctx.cover_letter
        if cover_letter is None and ctx.profile.cover_letter_template.strip():
            cover_letter = render_cover_letter(
                ctx.profile.cover_letter_template,
                company=ctx.company,
                job_title=ctx.job_title,
            )

        form = build_application_form_response(
            ctx.profile,
            config=ctx.config,
            company=ctx.company,
            cover_letter=cover_letter,
            resume_file=ctx.resume_file,
            include_resume_meta=True,
        )
        required = required_question_oids(job_detail)
        payload = build_apply_payload(form)
        if job_detail is not None:
            payload["job"] = {
                "uuid": job_detail.get("uuid"),
                "name": job_detail.get("name"),
                "companyName": job_detail.get("companyName"),
                "required_questions": required,
            }

        if ctx.dry_run:
            missing = missing_required_fields(form, required, live=False)
            if missing:
                return ApplyResult(
                    status="failed",
                    error=f"missing required Rippling fields: {', '.join(missing)}",
                    payload=payload,
                )
            return ApplyResult(status="dry_run", payload=payload)

        token = turnstile_token(ctx.credentials, ctx.config)
        if not token:
            return ApplyResult(
                status="failed",
                error=(
                    "rippling live apply requires Cloudflare Turnstile token in "
                    "credential session.cf_turnstile_token (public board apply is captcha-gated)"
                ),
                payload=payload,
            )

        if "resume" in required and ctx.resume_file is None:
            return ApplyResult(
                status="failed",
                error=(
                    "rippling live apply requires a stored resume file "
                    "on the application profile"
                ),
                payload=payload,
            )

        resume_url: str | None = None
        resume_ctype: str | None = None
        cover_url: str | None = None
        cover_ctype: str | None = None
        try:
            if ctx.resume_file is not None:
                resume_url, resume_ctype = upload_application_file(
                    self.http, board=board, resume_file=ctx.resume_file
                )
            if cover_letter and cover_letter.strip():
                cover_url, cover_ctype = upload_application_file(
                    self.http,
                    board=board,
                    content=cover_letter.strip().encode("utf-8"),
                    filename="cover-letter.txt",
                    content_type="text/plain",
                )
        except (ValueError, httpx.HTTPError) as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        form = build_application_form_response(
            ctx.profile,
            config=ctx.config,
            company=ctx.company,
            cover_letter=cover_letter,
            resume_file=ctx.resume_file,
            resume_url=resume_url,
            resume_content_type=resume_ctype,
            cover_letter_url=cover_url,
            cover_letter_content_type=cover_ctype,
            include_resume_meta=False,
        )
        missing = missing_required_fields(form, required, live=True)
        if missing:
            return ApplyResult(
                status="failed",
                error=f"missing required Rippling fields: {', '.join(missing)}",
                payload=build_apply_payload(form),
            )

        live_payload = build_apply_payload(form)
        headers = turnstile_headers(token)
        try:
            response = self.http.post_json(
                apply_url(board, job_id),
                json=live_payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            message = _http_error_message(exc)
            return ApplyResult(status="failed", error=message, payload=live_payload)

        if _response_has_error(response):
            return ApplyResult(
                status="failed",
                error=extract_error_message(response),
                payload=live_payload,
            )

        return ApplyResult(
            status="submitted",
            payload=live_payload,
            external_application_id=extract_application_id(response),
        )


def _response_has_error(response: object) -> bool:
    if not isinstance(response, dict):
        return False
    if response.get("error") or response.get("error_code"):
        return True
    return response.get("ok") is False


def _http_error_message(exc: httpx.HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            response.read()
            message = extract_error_message(response.json())
        except (httpx.HTTPError, ValueError, TypeError):
            message = str(exc)
        else:
            if message == "turnstile_verification_failure":
                return (
                    "rippling apply rejected Cloudflare Turnstile token "
                    "(turnstile_verification_failure)"
                )
            return message
    return str(exc)
