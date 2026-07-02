"""Meta Careers apply adapter.

Meta Careers has no public employer API. Applications are submitted through the
authenticated candidate portal Relay flow:

  POST /api/graphql/  (CandidateChatbotApplicationDetailSubmitMutation)
    -> xcp_create_application_v2

Public job metadata is available without login via
CandidatePortalJobDetailsViewQuery.

Config / context:
  - `config["requisition_id"]`: numeric Meta requisition id (optional if derivable).
  - Credential cookies: logged-in metacareers.com session.
  - Credential `session["session_id"]`: browser session key from the apply flow.
  - Credential `session["lsd"]` or `session["csrf_token"]`: optional anti-CSRF token.

Use `dry_run=True` to preview the mapped application state without authentication.
Live submit is best-effort and may require additional `profile.answers` mappings
for employer-specific questionnaires and EEO questions.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.meta_careers_common import (
    has_session_cookies,
    resolve_requisition_id,
    resolve_session_id,
)
from app.appliers.adapters.meta_careers_detail import fetch_job_detail
from app.appliers.adapters.meta_careers_live import (
    external_application_id,
    resolve_lsd_token,
    submit_application,
)
from app.appliers.adapters.meta_careers_payload import (
    build_application_payload,
    build_application_state,
    build_submit_input,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("meta_careers")
class MetaCareersApplier(Applier):
    """Submit (or preview) applications on Meta Careers."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        try:
            requisition_id = resolve_requisition_id(ctx.config, ctx.job_url, ctx.job_external_id)
            detail = fetch_job_detail(self.http, requisition_id)
            application_state = build_application_state(
                detail,
                ctx.profile,
                company=ctx.company,
                job_title=ctx.job_title,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
            )
            session_id = resolve_session_id(ctx.credentials, ctx.config)
            payload = build_application_payload(
                detail,
                ctx.profile,
                company=ctx.company,
                job_title=ctx.job_title,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
                session_id=session_id,
                include_submit_input=bool(session_id),
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        auth_error = _live_auth_error(session_id, ctx.credentials, payload)
        if auth_error is not None:
            return auth_error

        assert session_id is not None
        try:
            lsd = resolve_lsd_token(
                self.http,
                ctx.credentials,
                ctx.config,
                requisition_id=detail.requisition_id,
            )
            submit_input = build_submit_input(
                application_state,
                session_id=session_id,
                resume_file=ctx.resume_file,
                classic_view=bool(ctx.config.get("classic_view")),
                is_ra=bool(ctx.config.get("is_ra", True)),
            )
            payload["submit_input"] = submit_input
            response = submit_application(
                self.http,
                submit_input=submit_input,
                lsd=lsd,
                credentials=ctx.credentials,
                resume_file=ctx.resume_file,
                requisition_id=detail.requisition_id,
            )
        except (httpx.HTTPError, ValueError) as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        payload["submit_response"] = response
        return ApplyResult(
            status="submitted",
            payload=payload,
            external_application_id=external_application_id(response),
        )


def _live_auth_error(
    session_id: str | None,
    credentials: dict[str, dict[str, str]] | None,
    payload: dict[str, Any],
) -> ApplyResult | None:
    if not session_id:
        return ApplyResult(
            status="failed",
            error=(
                "meta_careers live apply requires credential session.session_id "
                "(browser session key from the Meta Careers apply flow)"
            ),
            payload=payload,
        )
    if not has_session_cookies(credentials):
        return ApplyResult(
            status="failed",
            error=(
                "meta_careers live apply requires logged-in Meta Careers "
                "cookies in site credentials"
            ),
            payload=payload,
        )
    return None
