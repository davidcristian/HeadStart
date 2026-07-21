"""Workable public careers apply adapter.

Submits applications via the undocumented public careers endpoints used by
``apply.workable.com/<account>/j/<shortcode>/apply``:

  GET  https://apply.workable.com/api/v1/jobs/<shortcode>/form
  GET  https://apply.workable.com/api/v1/jobs/<shortcode>/form/upload/resume
  POST https://apply.workable.com/api/v1/jobs/<shortcode>/apply

Config / context:
  - ``config["account"]``: optional account slug (also parsed from ``job_url``).
  - ``config["shortcode"]`` / ``job_id``: optional shortcode override.
  - Profile ``answers`` keys fill custom ``CA_*`` / ``QA_*`` / ``gdpr`` fields.
  - LinkedIn / GitHub / website profile links fill matching labeled questions.
  - Live submit requires Cloudflare Turnstile: credential
    ``session.cf_turnstile_token`` (or ``turnstile_token`` / config override).

Dry-run fetches the form schema and previews the candidate JSON (resume
metadata only). Live submit uploads the resume to Workable's presigned S3
bucket, then POSTs ``{candidate: …}`` with ``X-TURNSTILE-TOKEN``.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.workable_common import (
    apply_url,
    form_url,
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
from app.appliers.adapters.workable_resume import upload_resume
from app.appliers.base import Applier, register_applier
from app.appliers.text import render_cover_letter
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("workable")
class WorkableApplier(Applier):
    """Submit applications via Workable's public careers apply API."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        shortcode = resolve_shortcode(ctx.config, ctx.job_external_id, ctx.job_url)
        if not shortcode:
            return ApplyResult(
                status="failed",
                error=(
                    "workable applier needs a job shortcode in job_external_id, "
                    "config.shortcode, or an apply.workable.com/j/<shortcode> URL"
                ),
            )

        form = self._fetch_form(shortcode)
        cover_letter = ctx.cover_letter
        if cover_letter is None and ctx.profile.cover_letter_template.strip():
            cover_letter = render_cover_letter(
                ctx.profile.cover_letter_template,
                company=ctx.company,
                job_title=ctx.job_title,
            )

        candidate = build_candidate(
            ctx.profile,
            config=ctx.config,
            cover_letter=cover_letter,
            resume_file=ctx.resume_file,
            form=form,
            include_resume_meta=True,
        )
        required = required_field_ids(form)
        account = resolve_account(ctx.config, ctx.job_url)
        payload = _preview_payload(
            shortcode=shortcode,
            account=account,
            candidate=candidate,
            required=required,
            form=form,
        )

        if ctx.dry_run:
            missing = missing_required_fields(candidate, required, live=False)
            if missing:
                return ApplyResult(
                    status="failed",
                    error=f"missing required Workable fields: {', '.join(missing)}",
                    payload=payload,
                )
            return ApplyResult(status="dry_run", payload=payload)

        token = turnstile_token(ctx.credentials, ctx.config)
        if not token:
            return ApplyResult(
                status="failed",
                error=(
                    "workable live apply requires Cloudflare Turnstile token in "
                    "credential session.cf_turnstile_token "
                    "(public careers apply is captcha-gated)"
                ),
                payload=payload,
            )

        if "resume" in required and ctx.resume_file is None:
            return ApplyResult(
                status="failed",
                error=(
                    "workable live apply requires a stored resume file "
                    "on the application profile"
                ),
                payload=payload,
            )

        resume_url: str | None = None
        try:
            if ctx.resume_file is not None:
                resume_url = upload_resume(
                    self.http, shortcode=shortcode, resume_file=ctx.resume_file
                )
        except (ValueError, httpx.HTTPError) as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        candidate = build_candidate(
            ctx.profile,
            config=ctx.config,
            cover_letter=cover_letter,
            resume_file=ctx.resume_file,
            form=form,
            resume_url=resume_url,
            include_resume_meta=False,
        )
        missing = missing_required_fields(candidate, required, live=True)
        if missing:
            return ApplyResult(
                status="failed",
                error=f"missing required Workable fields: {', '.join(missing)}",
                payload=_preview_payload(
                    shortcode=shortcode,
                    account=account,
                    candidate=candidate,
                    required=required,
                    form=form,
                ),
            )

        live_payload = {"candidate": candidate}
        headers = turnstile_headers(token)
        try:
            response = self.http.post_json(
                apply_url(shortcode),
                json=live_payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(
                status="failed",
                error=_http_error_message(exc),
                payload=live_payload,
            )

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

    def _fetch_form(self, shortcode: str) -> list[Any] | None:
        try:
            raw = self.http.get_json(form_url(shortcode))
        except httpx.HTTPError:
            return None
        return raw if isinstance(raw, list) else None


def _preview_payload(
    *,
    shortcode: str,
    account: str | None,
    candidate: dict[str, Any],
    required: list[str],
    form: list[Any] | None,
) -> dict[str, Any]:
    preview: dict[str, Any] = {
        "shortcode": shortcode,
        "candidate": candidate,
        "required_fields": required,
    }
    if account:
        preview["account"] = account
    if form is not None:
        preview["form"] = form
    return preview


def _response_has_error(response: object) -> bool:
    if not isinstance(response, dict):
        return False
    # Informational ``message`` alone is not a failure (success payloads may set it).
    if response.get("error") or response.get("errors"):
        return True
    return response.get("ok") is False


def _http_error_message(exc: httpx.HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            response.read()
            body: object
            try:
                body = response.json()
            except ValueError:
                body = response.text
            message = extract_error_message(body)
        except httpx.HTTPError:
            message = str(exc)
        else:
            status = response.status_code
            if status == 409:
                return "workable apply rejected Cloudflare Turnstile token " f"({message})"
            if status == 412:
                return (
                    "workable apply precondition failed — ensure a fresh "
                    f"X-TURNSTILE-TOKEN is supplied ({message})"
                )
            return message
    return str(exc)
