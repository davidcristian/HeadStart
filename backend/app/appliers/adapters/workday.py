"""Workday job-board apply adapter.

Workday career sites use the CXS apply flow:
  1. POST /wday/cxs/{tenant}/jobpostings/{jobPostingId}/jobapplications
  2. POST /wday/cxs/{tenant}/jobapplication/{applicationId}/name
  3. POST /wday/cxs/{tenant}/jobapplication/{applicationId}/name
  4. POST /wday/cxs/{tenant}/attachments then POST .../resumeattachments (when profile has a file)
  5. POST .../workexperiences and .../educations (when profile has structured rows)
  6. POST .../skills and .../languages (when profile has structured rows)
  7. POST questionnaire responses (primary / secondary / supplementary)
  8. PUT /wday/cxs/{tenant}/jobapplication/{applicationId}/termsandconditions (optional)
  9. POST /wday/cxs/{tenant}/jobapplication/{applicationId}/finalize

Live submission requires an authenticated candidate session — store the
``CALYPSO_SESSION`` and ``CALYPSO_CSRF_TOKEN`` cookies (or
``session.csrf_token``) from a logged-in apply page in [site
credentials](../../docs/modules/credentials.md). Map screening questions via
``profile.answers`` (question id -> answer id or label). Uploaded resume files
are sent via the CXS attachments API; plain ``resume_text`` is a fallback in the
preview payload comments field when no file is stored.
"""

from __future__ import annotations

import httpx

from app.appliers.adapters.workday_common import (
    build_application_payload,
    resolve_csrf_token,
    resolve_job_path,
    resolve_job_posting_id,
    resolve_target,
)
from app.appliers.adapters.workday_experience import preview_educations, preview_work_experiences
from app.appliers.adapters.workday_skills import preview_languages, preview_skills
from app.appliers.adapters.workday_questionnaire import preview_questionnaires
from app.appliers.adapters.workday_resume import preview_resume_attachment
from app.appliers.adapters.workday_submit import submit_live_application
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult


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
                has_resume_file=ctx.resume_file is not None,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            preview = preview_questionnaires(
                self.http,
                target=target,
                config=ctx.config,
                profile=ctx.profile,
                job_path=job_path,
                credentials=ctx.credentials,
                csrf_token=resolve_csrf_token(ctx.credentials, ctx.config),
                session_id=None,
            )
            payload["questionnaires"] = preview.get("questionnaires", {})
            payload["jobPostingInfo"] = preview.get("jobPostingInfo", {})
            resume_preview = preview_resume_attachment(ctx.resume_file)
            if resume_preview is not None:
                payload["resumeAttachments"] = resume_preview
            work_experiences = preview_work_experiences(ctx.profile)
            if work_experiences:
                payload["workExperiences"] = work_experiences
            educations = preview_educations(ctx.profile)
            if educations:
                payload["educations"] = educations
            skills = preview_skills(ctx.profile)
            if skills:
                payload["skills"] = skills
            languages = preview_languages(ctx.profile)
            if languages:
                payload["languages"] = languages
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

        try:
            return submit_live_application(
                self.http,
                target=target,
                job_path=job_path,
                job_posting_id=job_posting_id,
                profile_payload=payload,
                profile=ctx.profile,
                resume_file=ctx.resume_file,
                config=ctx.config,
                csrf_token=csrf_token,
                credentials=ctx.credentials,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)
