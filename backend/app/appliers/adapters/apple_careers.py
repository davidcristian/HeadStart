"""Apple Careers apply adapter.

Apple Careers has no public employer API. Applications are submitted through the
authenticated jobs.apple.com talent endpoints:

  PUT  /api/v1/js/talent/<talentId>/applyJob
  POST /api/v1/js/talent/<talentId>/file/uploadFile
  GET  /api/v1/js/jobDetails/<jobId>/questionnaire

Config / context:
  - `config["locale"]`: path locale (default ``en-us``).
  - `config["post_locations"]` / `config["store_locations"]`: optional location
    objects for retail roles that require store selection.
  - Credential cookies: logged-in Apple Careers session from jobs.apple.com.
  - Credential `session["talent_id"]` and `session["csrf_token"]`.

Use `dry_run=True` to preview the mapped talent/roles payload without
authentication. Live submit is best-effort and may require additional
`profile.answers` mappings for employer-specific questionnaires.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.apple_careers_common import (
    apply_error_message,
    extract_application_id,
    has_session_cookies,
    resolve_csrf_token,
    resolve_job_detail_url,
    resolve_talent_id,
)
from app.appliers.adapters.apple_careers_detail import (
    AppleCareersJobDetail,
    fetch_job_detail,
)
from app.appliers.adapters.apple_careers_live import (
    fetch_questionnaire,
    questionnaire_answers,
    submit_apply_job,
    upload_resume,
)
from app.appliers.adapters.apple_careers_payload import (
    build_application_payload,
    build_apply_body,
    build_contact,
    build_roles,
    build_talent,
    resolve_post_locations,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("apple_careers")
class AppleCareersApplier(Applier):
    """Submit (or preview) applications on Apple Careers."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        detail_url = resolve_job_detail_url(ctx.config, ctx.job_url, ctx.job_external_id)
        if not detail_url:
            return ApplyResult(
                status="failed",
                error=(
                    "apple_careers applier needs a jobs.apple.com job URL or "
                    "config.job_detail_url"
                ),
            )

        try:
            detail = fetch_job_detail(self.http, detail_url)
            post_locations = resolve_post_locations(detail, ctx.config, ctx.profile)
            _validate_locations(detail, post_locations)
            contact = build_contact(ctx.profile)
            talent_id = resolve_talent_id(ctx.credentials, ctx.config)
            preview_talent_id = talent_id or "preview-talent-id"
            talent = build_talent(ctx.profile, talent_id=preview_talent_id, contact=contact)
            roles = build_roles(
                detail,
                talent_id=preview_talent_id,
                post_locations=post_locations,
            )
            apply_body = build_apply_body(
                detail=detail,
                talent_id=preview_talent_id,
                talent=talent,
                roles=roles,
            )
            payload = build_application_payload(
                detail=detail,
                profile=ctx.profile,
                talent_id=talent_id,
                post_locations=post_locations,
                contact=contact,
                talent=talent,
                roles=roles,
                apply_body=apply_body,
                resume_file=ctx.resume_file,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        auth_error = _live_auth_error(talent_id, ctx.credentials, payload)
        if auth_error is not None:
            return auth_error

        csrf_token = resolve_csrf_token(ctx.credentials, ctx.config)
        if not csrf_token:
            return ApplyResult(
                status="failed",
                error=(
                    "apple_careers live apply requires credential session.csrf_token "
                    "(from GET /api/v1/js/CSRFToken)"
                ),
                payload=payload,
            )

        try:
            assert talent_id is not None
            questionnaire = fetch_questionnaire(self.http, detail, csrf_token, ctx)
            answers = questionnaire_answers(questionnaire, ctx.profile.answers)
            resume_ref = None
            if ctx.resume_file is not None:
                resume_ref = upload_resume(
                    self.http,
                    talent_id,
                    ctx.resume_file,
                    csrf_token=csrf_token,
                    ctx=ctx,
                    detail=detail,
                )
            roles = build_roles(
                detail,
                talent_id=talent_id,
                post_locations=post_locations,
                resume_ref=resume_ref,
            )
            talent = build_talent(ctx.profile, talent_id=talent_id, contact=contact)
            apply_body = build_apply_body(
                detail=detail,
                talent_id=talent_id,
                talent=talent,
                roles=roles,
                questionnaire_answers=answers,
            )
            payload = build_application_payload(
                detail=detail,
                profile=ctx.profile,
                talent_id=talent_id,
                post_locations=post_locations,
                contact=contact,
                talent=talent,
                roles=roles,
                apply_body=apply_body,
                resume_file=ctx.resume_file,
                questionnaire=questionnaire,
            )
            response = submit_apply_job(
                self.http,
                talent_id,
                apply_body,
                csrf_token=csrf_token,
                ctx=ctx,
                detail=detail,
            )
        except (httpx.HTTPError, ValueError) as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        error = apply_error_message(response)
        if error is not None:
            return ApplyResult(status="failed", error=error, payload=payload)

        return ApplyResult(
            status="submitted",
            payload=payload,
            external_application_id=extract_application_id(response),
        )


def _validate_locations(
    detail: AppleCareersJobDetail,
    post_locations: list[dict[str, Any]],
) -> None:
    if detail.role_location_selection and not post_locations:
        raise ValueError(
            "apple_careers retail roles require config.store_locations or "
            "config.post_locations with the selected store/post location objects"
        )


def _live_auth_error(
    talent_id: str | None,
    credentials: dict[str, dict[str, str]] | None,
    payload: dict[str, Any],
) -> ApplyResult | None:
    if not talent_id:
        return ApplyResult(
            status="failed",
            error=(
                "apple_careers live apply requires credential session.talent_id "
                "or config.talent_id"
            ),
            payload=payload,
        )
    if not has_session_cookies(credentials):
        return ApplyResult(
            status="failed",
            error=(
                "apple_careers live apply requires logged-in Apple Careers "
                "cookies in site credentials"
            ),
            payload=payload,
        )
    return None
