"""Live OData submit helpers for the SuccessFactors apply adapter."""

from __future__ import annotations

from typing import Any

import httpx

from app.appliers.adapters.successfactors_common import (
    attachment_url,
    candidate_url,
    extract_entity_id,
    extract_error_message,
    http_error_message,
    job_application_url,
    json_bytes,
    odata_reports_error,
    response_json,
)
from app.appliers.adapters.successfactors_payload import (
    build_application_payload,
    build_attachment_payload,
    build_dry_run_payload,
)
from app.appliers.types import ApplyContext, ApplyResult
from app.scrapers.http import HttpClient


def live_submit(
    http: HttpClient,
    ctx: ApplyContext,
    *,
    headers: dict[str, str],
    odata_base: str,
    company_id: str,
    job_id: str,
    careers_base: str | None,
    apply_url: str | None,
    locale: str,
    candidate: dict[str, Any],
    cover_letter: str | None,
    attachment_preview: dict[str, Any] | None,
    preview: dict[str, Any],
) -> ApplyResult:
    """POST Candidate → optional Attachment → JobApplication."""
    try:
        candidate_resp = http.post_raw(
            candidate_url(odata_base),
            content=json_bytes(candidate),
            headers=headers,
        )
    except httpx.HTTPError as exc:
        return ApplyResult(
            status="failed",
            error=http_error_message(exc),
            payload=preview,
        )

    candidate_body = response_json(candidate_resp)
    candidate_id = extract_entity_id(candidate_body, "candidateId", "id")
    if not candidate_id:
        return ApplyResult(
            status="failed",
            error=(
                extract_error_message(candidate_body)
                if odata_reports_error(candidate_body)
                else "successfactors Candidate create did not return candidateId"
            ),
            payload={**preview, "candidate_response": candidate_body},
        )

    attachment_id, attachment_body, attach_error = _upload_resume(
        http,
        ctx,
        headers=headers,
        odata_base=odata_base,
        candidate_id=candidate_id,
        candidate_body=candidate_body,
        preview=preview,
    )
    if attach_error is not None:
        return attach_error

    live_application = build_application_payload(
        ctx.profile,
        job_req_id=job_id,
        candidate_id=candidate_id,
        cover_letter=cover_letter,
        attachment_id=attachment_id,
        config=ctx.config,
    )
    live_payload = build_dry_run_payload(
        candidate=candidate,
        application=live_application,
        job_id=job_id,
        careers_base_url=careers_base,
        apply_url=apply_url,
        odata_base_url=odata_base,
        company_id=company_id,
        locale=locale,
        resume_file=ctx.resume_file,
        attachment=attachment_preview,
    )
    live_payload["candidate_id"] = candidate_id
    live_payload["candidate_response"] = candidate_body
    if attachment_id:
        live_payload["attachment_id"] = attachment_id
        live_payload["attachment_response"] = attachment_body

    try:
        application_resp = http.post_raw(
            job_application_url(odata_base),
            content=json_bytes(live_application),
            headers=headers,
        )
    except httpx.HTTPError as exc:
        return ApplyResult(
            status="failed",
            error=http_error_message(exc),
            payload=live_payload,
        )

    application_body = response_json(application_resp)
    application_id = extract_entity_id(application_body, "applicationId", "jobApplicationId", "id")
    if not application_id and odata_reports_error(application_body):
        return ApplyResult(
            status="failed",
            error=extract_error_message(application_body),
            payload={**live_payload, "application_response": application_body},
        )

    live_payload["application_response"] = application_body
    live_payload["application_id"] = application_id
    return ApplyResult(
        status="submitted",
        external_application_id=application_id or candidate_id,
        payload=live_payload,
    )


def _upload_resume(
    http: HttpClient,
    ctx: ApplyContext,
    *,
    headers: dict[str, str],
    odata_base: str,
    candidate_id: str,
    candidate_body: object,
    preview: dict[str, Any],
) -> tuple[str | None, object | None, ApplyResult | None]:
    """Upload resume Attachment when present; return id/body or failure."""
    if ctx.resume_file is None:
        return None, None, None
    try:
        attachment_resp = http.post_raw(
            attachment_url(odata_base),
            content=json_bytes(build_attachment_payload(ctx.resume_file)),
            headers=headers,
        )
    except httpx.HTTPError as exc:
        return (
            None,
            None,
            ApplyResult(
                status="failed",
                error=http_error_message(exc),
                payload={
                    **preview,
                    "candidate_id": candidate_id,
                    "candidate_response": candidate_body,
                },
            ),
        )
    attachment_body = response_json(attachment_resp)
    attachment_id = extract_entity_id(attachment_body, "attachmentId", "id")
    if not attachment_id:
        return (
            None,
            None,
            ApplyResult(
                status="failed",
                error=(
                    extract_error_message(attachment_body)
                    if odata_reports_error(attachment_body)
                    else "successfactors Attachment create did not return attachmentId"
                ),
                payload={
                    **preview,
                    "candidate_id": candidate_id,
                    "candidate_response": candidate_body,
                    "attachment_response": attachment_body,
                },
            ),
        )
    return attachment_id, attachment_body, None
