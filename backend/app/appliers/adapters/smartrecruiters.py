"""SmartRecruiters job-board apply adapter.

Submits applications via the SmartRecruiters Application API:
  GET  https://api.smartrecruiters.com/postings/<uuid>/configuration
  POST https://api.smartrecruiters.com/postings/<uuid>/candidates

Posting UUIDs are resolved from the public Postings detail API when needed:
  GET https://api.smartrecruiters.com/v1/companies/<company_id>/postings/<id>

Config / context:
  - `config["company_id"]`: company slug from careers.smartrecruiters.com/<slug>.
  - `config["posting_uuid"]`: optional posting UUID override.
  - `config["smart_token"]`: Application API token (`X-SmartToken`) for live submit.
  - Credential `session["smart_token"]` or `session["access_token"]` overrides config.
  - `config["gdpr_consent"]`: when true, sets consentDecisions on the payload.
  - Profile `answers` keys: `sr_<question_id>`, `<question_id>`, or `question_<question_id>`.

Live submission requires a SmartRecruiters Application API token or OAuth bearer token.
Use `dry_run=True` to preview payloads without credentials.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.smartrecruiters_common import (
    APPLY_URL,
    auth_headers,
    resolve_company_id,
    resolve_posting_uuid,
)
from app.appliers.adapters.smartrecruiters_configuration import (
    fetch_configuration,
    required_question_ids,
)
from app.appliers.adapters.smartrecruiters_payload import (
    build_application_payload,
    extract_application_id,
    extract_error_message,
)
from app.appliers.adapters.smartrecruiters_questions import (
    build_screening_answers,
    missing_required_answers,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("smartrecruiters")
class SmartRecruitersApplier(Applier):
    """Submit applications to a SmartRecruiters public careers board."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        company_id = resolve_company_id(ctx.config, ctx.job_url)
        if not company_id:
            return ApplyResult(
                status="failed",
                error=(
                    "smartrecruiters applier needs config.company_id "
                    "or a jobs.smartrecruiters.com job URL"
                ),
            )

        try:
            posting_uuid = resolve_posting_uuid(
                ctx.config,
                ctx.job_external_id,
                company_id=company_id,
                http=self.http,
            )
        except (ValueError, httpx.HTTPError) as exc:
            return ApplyResult(status="failed", error=str(exc))

        headers = auth_headers(ctx.credentials, ctx.config)
        configuration: dict[str, Any] | None = None
        if headers:
            try:
                configuration = fetch_configuration(
                    self.http,
                    posting_uuid,
                    headers=headers,
                    conditionals_included=bool(ctx.config.get("include_conditional_questions")),
                )
            except httpx.HTTPError as exc:
                if not ctx.dry_run:
                    return ApplyResult(status="failed", error=str(exc))

        try:
            payload = build_application_payload(
                ctx.profile,
                company=ctx.company,
                job_title=ctx.job_title,
                config=ctx.config,
                configuration=configuration,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
                include_file_bytes=not ctx.dry_run,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        envelope: dict[str, Any] = {
            "posting_uuid": posting_uuid,
            "company_id": company_id,
            "candidate": payload,
        }
        if configuration is not None:
            envelope["configuration_questions"] = len(configuration.get("questions") or [])
            envelope["required_question_ids"] = required_question_ids(configuration)
            envelope["missing_required_question_ids"] = missing_required_answers(
                configuration,
                ctx.profile.answers,
            )
            if not payload.get("answers"):
                payload["answers"] = build_screening_answers(configuration, ctx.profile.answers)

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=envelope)

        if not headers:
            return ApplyResult(
                status="failed",
                error=(
                    "smartrecruiters live apply requires an Application API token in "
                    "credential session.smart_token / session.access_token or "
                    "config.smart_token / config.access_token"
                ),
                payload=envelope,
            )

        missing = missing_required_answers(configuration, ctx.profile.answers)
        if missing:
            return ApplyResult(
                status="failed",
                error=(
                    "smartrecruiters apply is missing required screening answers for: "
                    + ", ".join(missing)
                ),
                payload=envelope,
            )

        url = APPLY_URL.format(posting_uuid=posting_uuid)
        try:
            response = self.http.post_json(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=envelope)

        if (
            isinstance(response, dict)
            and response.get("message")
            and not response.get("applicationId")
        ):
            return ApplyResult(
                status="failed",
                error=extract_error_message(response),
                payload=envelope,
            )

        app_id = extract_application_id(response)
        return ApplyResult(status="submitted", payload=envelope, external_application_id=app_id)
