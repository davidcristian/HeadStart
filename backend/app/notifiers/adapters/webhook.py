"""Generic JSON webhook notifier for power-user integrations.

POSTs structured job payloads to any HTTPS endpoint (Zapier, n8n, custom scripts).
Unlike Slack/Discord adapters, messages are machine-readable JSON rather than
channel-specific formatting.

Target config:
    {
      "webhook_url": "https://example.com/hooks/headstart",  # required
      "secret": "optional-hmac-signing-key",                   # optional
      "headers": { "X-Custom": "value" }                       # optional
    }
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.core.logging import get_logger
from app.core.outbound_http import pinned_request
from app.core.outbound_url import UnsafeOutboundUrlError, assert_safe_outbound_url
from app.notifiers.base import Notifier, register_notifier
from app.notifiers.http_errors import safe_http_error
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting

logger = get_logger(__name__)

_SIGNATURE_HEADER = "X-HeadStart-Signature"
# User `headers` must not override the JSON content type or HMAC signature.
_RESERVED_HEADER_NAMES = frozenset({"content-type", _SIGNATURE_HEADER.lower()})


@register_notifier("webhook")
class WebhookNotifier(Notifier):
    """Deliver new jobs as JSON POSTs to a user-configured webhook URL."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        webhook_url = ctx.config.get("webhook_url")
        if not webhook_url or not str(webhook_url).strip():
            raise ValueError("webhook target requires config.webhook_url")

        url = str(webhook_url).strip()
        try:
            assert_safe_outbound_url(url)
        except UnsafeOutboundUrlError as exc:
            raise ValueError(str(exc)) from exc

        if ctx.digest:
            return self._send_digest(url, ctx, jobs)

        results: list[DeliveryResult] = []
        for job in jobs:
            results.append(self._send_one(url, ctx, job))
        return results

    def _send_digest(
        self, webhook_url: str, ctx: NotifyContext, jobs: list[JobPosting]
    ) -> list[DeliveryResult]:
        if not jobs:
            return []
        payload = {
            "event": "jobs.digest",
            "search_name": ctx.search_name,
            "count": len(jobs),
            "jobs": [_job_payload(job) for job in jobs],
        }
        try:
            self._post(webhook_url, ctx, payload)
            return [DeliveryResult(external_id=job.external_id, status="sent") for job in jobs]
        except httpx.HTTPError as exc:
            safe = safe_http_error(exc, webhook_url)
            logger.warning("webhook digest send failed: %s", safe)
            return [
                DeliveryResult(external_id=job.external_id, status="failed", error=safe)
                for job in jobs
            ]

    def _send_one(self, webhook_url: str, ctx: NotifyContext, job: JobPosting) -> DeliveryResult:
        payload = {"event": "job.new", "job": _job_payload(job)}
        try:
            self._post(webhook_url, ctx, payload)
            return DeliveryResult(external_id=job.external_id, status="sent")
        except httpx.HTTPError as exc:
            safe = safe_http_error(exc, webhook_url)
            logger.warning("webhook send failed for %s: %s", job.external_id, safe)
            return DeliveryResult(external_id=job.external_id, status="failed", error=safe)

    def _post(self, webhook_url: str, ctx: NotifyContext, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers = _request_headers(ctx, body)
        resp = pinned_request(self._client, "POST", webhook_url, content=body, headers=headers)
        resp.raise_for_status()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _job_payload(job: JobPosting) -> dict[str, Any]:
    """Serialize a posting for webhook consumers."""
    return {
        "external_id": job.external_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "summary": job.summary,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
    }


def _request_headers(ctx: NotifyContext, body: bytes) -> dict[str, str]:
    """Build POST headers; reserved Content-Type / signature always win over user config."""
    headers = {"Content-Type": "application/json"}
    extra = ctx.config.get("headers")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if not key or value is None:
                continue
            name = str(key)
            if name.lower() in _RESERVED_HEADER_NAMES:
                continue
            headers[name] = str(value)

    secret = ctx.config.get("secret")
    if secret and str(secret).strip():
        digest = hmac.new(str(secret).encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers[_SIGNATURE_HEADER] = f"sha256={digest}"

    return headers
