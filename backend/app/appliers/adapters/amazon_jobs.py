"""Amazon Jobs (amazon.jobs) apply adapter.

Amazon's applicant portal exposes JSON endpoints on www.amazon.jobs:

  PUT  /api/apply/applicant/
  POST /api/apply/documents
  POST /api/apply/jobs/<id>/application/draft_application
  POST /api/apply/jobs/<id>/application/submit_application

Config / context:
  - `config["locale"]`: path locale (default ``en``).
  - `config["job_id"]` / `config["id_icims"]`: optional override for the iCIMS id.
  - `config["recruiting_source"]`: optional draft-application source tag.
  - Credential cookies: logged-in amazon.jobs / account.amazon.jobs session.

Use `dry_run=True` to preview the mapped applicant body and apply URLs without
authentication. Live submit requires the candidate's own logged-in session.
"""

from __future__ import annotations

import httpx

from app.appliers.adapters.amazon_jobs_common import (
    api_error_message,
    apply_page_url,
    documents_url,
    draft_application_url,
    extract_application_id,
    has_session_cookies,
    request_headers,
    resolve_job_id,
    resolve_locale,
    submit_application_url,
)
from app.appliers.adapters.amazon_jobs_detail import fetch_public_job_detail
from app.appliers.adapters.amazon_jobs_payload import (
    build_applicant_body,
    build_application_payload,
)
from app.appliers.base import Applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult
from app.schemas.profile import ResumeFile
from app.scrapers.http import HttpClient


@register_applier("amazon_jobs")
class AmazonJobsApplier(Applier):
    """Submit (or preview) applications on amazon.jobs."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        locale = resolve_locale(ctx.config)
        job_id = resolve_job_id(ctx.config, ctx.job_url, ctx.job_external_id)
        if not job_id:
            return ApplyResult(
                status="failed",
                error=(
                    "amazon_jobs applier needs a job id from job_external_id, "
                    "config.job_id, or an /jobs/<id> URL"
                ),
            )

        recruiting_source = str(ctx.config.get("recruiting_source") or "").strip() or None

        try:
            detail = fetch_public_job_detail(self.http, locale=locale, job_id=job_id)
            payload = build_application_payload(
                detail,
                ctx.profile,
                company=ctx.company,
                job_title=ctx.job_title,
                cover_letter=ctx.cover_letter,
                resume_file=ctx.resume_file,
                recruiting_source=recruiting_source,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))
        except httpx.HTTPError as exc:
            return ApplyResult(status="failed", error=str(exc))

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=payload)

        if not has_session_cookies(ctx.credentials):
            return ApplyResult(
                status="failed",
                error=(
                    "amazon_jobs live apply requires logged-in amazon.jobs "
                    "session cookies in site credentials"
                ),
                payload=payload,
            )

        referer = apply_page_url(job_id)
        headers = request_headers(referer=referer, credentials=ctx.credentials)
        http = self.http

        try:
            applicant_body = build_applicant_body(
                ctx.profile,
                cover_letter=ctx.cover_letter,
                company=ctx.company,
                job_title=ctx.job_title,
            )
            update_response = http.put_json(
                payload["applicant_update"]["url"],
                json=applicant_body,
                headers=headers,
            )
            error = api_error_message(update_response)
            if error:
                return ApplyResult(status="failed", error=error, payload=payload)

            if ctx.resume_file is not None:
                self._upload_resume(http, ctx.resume_file, headers=headers, referer=referer)

            draft_body = payload["draft_application"]["body"]
            draft_response = http.post_json(
                draft_application_url(job_id),
                json=draft_body,
                headers=headers,
            )
            error = api_error_message(draft_response)
            if error:
                return ApplyResult(status="failed", error=error, payload=payload)

            submit_response = http.post_json(
                submit_application_url(job_id),
                json={},
                headers=headers,
            )
            error = api_error_message(submit_response)
            if error:
                return ApplyResult(status="failed", error=error, payload=payload)
        except (httpx.HTTPError, ValueError) as exc:
            return ApplyResult(status="failed", error=str(exc), payload=payload)

        app_id = extract_application_id(submit_response) or extract_application_id(draft_response)
        return ApplyResult(
            status="submitted",
            payload=payload,
            external_application_id=app_id,
        )

    def _upload_resume(
        self,
        http: HttpClient,
        resume_file: ResumeFile,
        *,
        headers: dict[str, str],
        referer: str,
    ) -> None:
        """Upload the stored resume file to amazon.jobs documents."""
        upload_headers = {
            key: value for key, value in headers.items() if key.lower() != "content-type"
        }
        upload_headers["Referer"] = referer
        response = http.post_multipart(
            documents_url(),
            data={"document_type": "resume"},
            files={"file": (resume_file.filename, resume_file.data, resume_file.content_type)},
            headers=upload_headers,
        )
        error = api_error_message(response)
        if error:
            raise ValueError(error)
