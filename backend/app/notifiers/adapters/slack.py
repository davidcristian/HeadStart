"""Slack incoming-webhook notifier.

Posts one message per new job to a Slack channel via an incoming webhook URL.
Create the webhook in Slack: Apps → Incoming Webhooks → Add to Slack.

Target config:
    {
      "webhook_url": "https://hooks.slack.com/services/T00/B00/xxxx"  # required
    }
"""

from typing import Any

import httpx

from app.core.logging import get_logger
from app.core.outbound_http import pinned_request
from app.core.outbound_url import UnsafeOutboundUrlError, assert_safe_outbound_url
from app.notifiers.base import Notifier, register_notifier
from app.notifiers.digest_format import digest_blocks, digest_title
from app.notifiers.http_errors import safe_http_error
from app.notifiers.markup import escape_slack_mrkdwn, slack_apply_link
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting

logger = get_logger(__name__)


@register_notifier("slack")
class SlackNotifier(Notifier):
    """Send new jobs as Slack messages via an incoming webhook."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        webhook_url = ctx.config.get("webhook_url")
        if not webhook_url or not str(webhook_url).strip():
            raise ValueError("slack target requires config.webhook_url")

        url = str(webhook_url).strip()
        try:
            assert_safe_outbound_url(url)
        except UnsafeOutboundUrlError as exc:
            raise ValueError(str(exc)) from exc

        if ctx.digest:
            return self._send_digest(url, ctx, jobs)

        results: list[DeliveryResult] = []
        for job in jobs:
            results.append(self._send_one(url, job))
        return results

    def _send_digest(
        self, webhook_url: str, ctx: NotifyContext, jobs: list[JobPosting]
    ) -> list[DeliveryResult]:
        if not jobs:
            return []
        payload = self._digest_payload(ctx, jobs)
        try:
            resp = pinned_request(self._client, "POST", webhook_url, json=payload)
            resp.raise_for_status()
            return [DeliveryResult(external_id=job.external_id, status="sent") for job in jobs]
        except httpx.HTTPError as exc:
            safe = safe_http_error(exc, webhook_url)
            logger.warning("slack digest send failed: %s", safe)
            return [
                DeliveryResult(external_id=job.external_id, status="failed", error=safe)
                for job in jobs
            ]

    def _send_one(self, webhook_url: str, job: JobPosting) -> DeliveryResult:
        payload = self._payload(job)
        try:
            resp = pinned_request(self._client, "POST", webhook_url, json=payload)
            resp.raise_for_status()
            return DeliveryResult(external_id=job.external_id, status="sent")
        except httpx.HTTPError as exc:
            safe = safe_http_error(exc, webhook_url)
            logger.warning("slack send failed for %s: %s", job.external_id, safe)
            return DeliveryResult(external_id=job.external_id, status="failed", error=safe)

    @staticmethod
    def _payload(job: JobPosting) -> dict[str, Any]:
        text = SlackNotifier._text(job)
        return {
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                }
            ],
        }

    @staticmethod
    def _digest_payload(ctx: NotifyContext, jobs: list[JobPosting]) -> dict[str, Any]:
        lines = [escape_slack_mrkdwn(digest_title(len(jobs), ctx.search_name)), ""]
        for block in digest_blocks(jobs):
            lines.append(f"• {escape_slack_mrkdwn(block.headline)}")
            if block.summary:
                lines.append(f"  {escape_slack_mrkdwn(block.summary)}")
            apply = slack_apply_link(block.url) if block.url else None
            if apply:
                lines.append(f"  {apply}")
        text = "\n".join(lines)
        return {
            "text": text,
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
        }

    @staticmethod
    def _text(job: JobPosting) -> str:
        title = f"*{escape_slack_mrkdwn(job.title)}*" if job.title else "New job"
        headline = f"{title} @ {escape_slack_mrkdwn(job.company)}" if job.company else title
        lines = [headline]
        if job.summary:
            lines.append(escape_slack_mrkdwn(job.summary))
        if job.location:
            lines.append(escape_slack_mrkdwn(job.location))
        apply = slack_apply_link(job.url) if job.url else None
        if apply:
            lines.append(apply)
        return "\n".join(lines)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
