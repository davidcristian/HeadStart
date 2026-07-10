"""Uber Careers apply adapter.

Uber's careers site uses a Fusion app with:

  POST /careers/apply/api/getAdditionalQuestionsForJob
  POST /careers/apply/graphql  (submitApplication mutation)

Config / context:
  - `config["locale"]`: API locale code (default ``en``).
  - `config["careers_locale_path"]`: careers URL prefix (default ``us/en``).
  - Credential `session["session_token"]` or `session["sessionToken"]`: logged-in
    Uber Careers session from ``doSignIn``.
  - Profile `answers` for EEO/screening fields: ``legal_right_to_work``, ``in_usa``,
    ``require_visa_sponsorship``, ``gender``/``sex``, ``disability``, ``veteran``,
    ``race``, ``sexual_orientation``, plus ``uber_<question_id>`` for job questions.

Use `dry_run=True` to preview the mapped application payload without authentication.
Live submit requires a valid Uber Careers session token.
"""

from __future__ import annotations

import httpx

from app.appliers.adapters.uber_careers_common import (
    apply_form_url,
    resolve_careers_locale_path,
    resolve_job_id,
    resolve_locale,
    resolve_session_token,
)
from app.appliers.adapters.uber_careers_graphql import submit_application
from app.appliers.adapters.uber_careers_payload import (
    build_application_form_request,
    build_application_payload,
)
from app.appliers.adapters.uber_careers_questions import (
    fetch_additional_questions,
    missing_required_answers,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("uber_careers")
class UberCareersApplier(Applier):
    """Submit (or preview) applications on Uber Careers."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        job_id = resolve_job_id(ctx.config, ctx.job_url, ctx.job_external_id)
        if job_id is None:
            return ApplyResult(
                status="failed",
                error=(
                    "uber_careers applier needs a numeric job id in job_external_id, "
                    "config.job_id, or an uber.com careers job URL"
                ),
            )

        locale = resolve_locale(ctx.config)
        locale_path = resolve_careers_locale_path(ctx.config)
        session_token = resolve_session_token(ctx.credentials, ctx.config)

        try:
            additional_questions = fetch_additional_questions(
                self.http,
                job_id=job_id,
                locale=locale,
                locale_path=locale_path,
            )
            missing = missing_required_answers(additional_questions, ctx.profile.answers)
            if missing and not ctx.dry_run:
                preview = ", ".join(missing[:5])
                suffix = "..." if len(missing) > 5 else ""
                return ApplyResult(
                    status="failed",
                    error=(
                        "uber_careers apply is missing required screening answers for: "
                        f"{preview}{suffix}"
                    ),
                )

            payload = build_application_payload(
                ctx.profile,
                job_id=job_id,
                job_title=ctx.job_title,
                company=ctx.company,
                additional_questions=additional_questions,
                resume_file=ctx.resume_file,
                cover_letter=ctx.cover_letter,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        if not session_token:
            return ApplyResult(
                status="failed",
                error=(
                    "uber_careers live apply requires credential session.session_token "
                    "from a logged-in Uber Careers account"
                ),
            )

        try:
            application_form_request = build_application_form_request(
                ctx.profile,
                job_id=job_id,
                job_title=ctx.job_title,
                session_token=session_token,
                additional_questions=additional_questions,
                resume_file=ctx.resume_file,
                include_resume_bytes=True,
            )
            referer = apply_form_url(job_id, locale_path=locale_path)
            result = submit_application(
                self.http,
                application_form_request=application_form_request,
                referer=referer,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc))

        payload["application_form_request"] = {
            key: value for key, value in application_form_request.items() if key != "attachments"
        }
        payload["attachments_submitted"] = bool(application_form_request.get("attachments"))
        external_id = str(result) if result is not None else str(job_id)
        return ApplyResult(
            status="submitted",
            payload=payload,
            external_application_id=external_id,
        )
