"""iCIMS / Jibe Attract apply adapter (Talent Cloud Partner API).

Public Jibe Attract careers sites expose listings via ``/api/jobs`` but route
applications through a login + captcha SPA (or an ``*.icims.com`` iframe). There
is no unauthenticated public apply POST comparable to Greenhouse/Rippling.

This adapter therefore uses the documented iCIMS Talent Cloud Partner API:

  POST https://api.icims.com/customers/<customer_id>/people
  POST https://api.icims.com/customers/<customer_id>/applicantworkflows

Config / context:
  - ``config["careers_base_url"]``: Jibe Attract origin (optional enrichment).
  - ``config["customer_id"]`` / ``tenant_id``: iCIMS customer id (required live).
  - ``config["job_id"]`` / ``req_id``: optional numeric job id override.
  - ``config["folder_id"]``, ``status_id``, ``application_source``, phone/address
    type ids, ``notes_field``, and ``icims_*`` profile answers for custom fields.
  - Credential ``session.username`` + ``session.password`` (aliases:
    ``basic_auth_*``, ``api_*``, ``icims_*``) for Partner API Basic Auth.

Dry-run builds the person + workflow JSON without calling the Partner API.
Live submit requires Partner Program credentials scoped to the customer.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import httpx

from app.appliers.adapters.icims_common import (
    applicant_workflows_url,
    basic_auth_header,
    extract_error_message,
    parse_created_id,
    people_url,
    resolve_basic_auth,
    resolve_careers_base_url,
    resolve_customer_id,
    resolve_job_id,
)
from app.appliers.adapters.icims_payload import (
    build_dry_run_payload,
    build_person_payload,
    build_workflow_payload,
)
from app.appliers.base import Applier, register_applier
from app.appliers.text import render_cover_letter
from app.appliers.types import ApplyContext, ApplyResult


@register_applier("icims")
class IcimsApplier(Applier):
    """Submit applications via the iCIMS Talent Cloud Partner API."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        job_id = resolve_job_id(ctx.config, ctx.job_external_id, ctx.job_url)
        if not job_id:
            return ApplyResult(
                status="failed",
                error=(
                    "icims applier needs a numeric job id in job_external_id, "
                    "config.job_id, or a /jobs/<id> URL"
                ),
            )

        careers_base = resolve_careers_base_url(ctx.config, ctx.job_url)
        job_detail = self._fetch_job_detail(careers_base, job_id) if careers_base else None
        customer_id = resolve_customer_id(ctx.config, ctx.credentials, job_detail)
        apply_url = None
        if isinstance(job_detail, dict):
            raw_apply = job_detail.get("apply_url")
            if isinstance(raw_apply, str) and raw_apply.strip():
                apply_url = raw_apply.strip()

        cover_letter = ctx.cover_letter
        if cover_letter is None and ctx.profile.cover_letter_template.strip():
            cover_letter = render_cover_letter(
                ctx.profile.cover_letter_template,
                company=ctx.company,
                job_title=ctx.job_title,
            )

        try:
            person = build_person_payload(
                ctx.profile,
                config=ctx.config,
                cover_letter=cover_letter,
                resume_file=ctx.resume_file,
            )
        except ValueError as exc:
            return ApplyResult(status="failed", error=str(exc))

        workflow = build_workflow_payload(job_id=job_id, person_id=None, config=ctx.config)
        preview = build_dry_run_payload(
            person=person,
            workflow=workflow,
            customer_id=customer_id,
            job_id=job_id,
            careers_base_url=careers_base,
            apply_url=apply_url,
            job_detail=job_detail,
        )

        if ctx.dry_run:
            return ApplyResult(status="dry_run", payload=preview)

        if not customer_id:
            return ApplyResult(
                status="failed",
                error=(
                    "icims live apply requires config.customer_id (or tenant_id) "
                    "because public Jibe apply is login/captcha gated; use Talent "
                    "Cloud Partner API credentials scoped to the employer"
                ),
                payload=preview,
            )

        auth = resolve_basic_auth(ctx.credentials, ctx.config)
        if auth is None:
            return ApplyResult(
                status="failed",
                error=(
                    "icims live apply requires Partner API Basic Auth in "
                    "credential session.username + session.password "
                    "(aliases: basic_auth_*, api_*, icims_*)"
                ),
                payload=preview,
            )

        headers = {
            "Authorization": basic_auth_header(*auth),
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
        }
        try:
            person_resp = self.http.post_raw(
                people_url(customer_id),
                content=_json_bytes(person),
                headers=headers,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(
                status="failed",
                error=_http_error_message(exc),
                payload=preview,
            )

        person_id = parse_created_id(person_resp.headers.get("Location"))
        if not person_id:
            return ApplyResult(
                status="failed",
                error="icims people create did not return a Location profile id",
                payload=preview,
            )

        live_workflow = build_workflow_payload(
            job_id=job_id, person_id=person_id, config=ctx.config
        )
        live_payload = build_dry_run_payload(
            person=person,
            workflow=live_workflow,
            customer_id=customer_id,
            job_id=job_id,
            careers_base_url=careers_base,
            apply_url=apply_url,
            job_detail=job_detail,
        )
        live_payload["person_id"] = person_id

        try:
            workflow_resp = self.http.post_raw(
                applicant_workflows_url(customer_id),
                content=_json_bytes(live_workflow),
                headers=headers,
            )
        except httpx.HTTPError as exc:
            return ApplyResult(
                status="failed",
                error=_http_error_message(exc),
                payload=live_payload,
            )

        workflow_id = parse_created_id(workflow_resp.headers.get("Location"))
        live_payload["workflow_id"] = workflow_id
        return ApplyResult(
            status="submitted",
            payload=live_payload,
            external_application_id=workflow_id or person_id,
        )

    def _fetch_job_detail(self, careers_base: str, job_id: str) -> dict[str, Any] | None:
        """Best-effort job row from the public Jibe ``/api/jobs`` list endpoint."""
        params = urlencode({"page": 1, "limit": 50, "keywords": job_id})
        url = f"{careers_base.rstrip('/')}/api/jobs?{params}"
        try:
            data = self.http.get_json(url)
        except httpx.HTTPError:
            return None
        if not isinstance(data, dict):
            return None
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            return None
        for raw in jobs:
            if not isinstance(raw, dict):
                continue
            row_obj = raw.get("data")
            row = row_obj if isinstance(row_obj, dict) else raw
            slug = str(row.get("slug") or row.get("req_id") or "").strip()
            if slug == job_id:
                return row
        return None


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _http_error_message(exc: httpx.HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return str(exc)
    try:
        response.read()
        return extract_error_message(response.json())
    except (httpx.HTTPError, ValueError, TypeError):
        return str(exc)


__all__ = ["IcimsApplier"]
