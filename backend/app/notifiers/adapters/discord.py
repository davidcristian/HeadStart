"""Discord incoming-webhook notifier.

Posts one message per new job to a Discord channel via a webhook URL.
Create the webhook in Discord: Server Settings → Integrations → Webhooks.

Target config:
    {
      "webhook_url": "https://discord.com/api/webhooks/123/abc..."  # required
    }
"""

from typing import Any

import httpx

from app.core.logging import get_logger
from app.notifiers.base import Notifier, register_notifier
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting

logger = get_logger(__name__)

_EMBED_COLOR = 0x5865F2  # Discord blurple


@register_notifier("discord")
class DiscordNotifier(Notifier):
    """Send new jobs as Discord messages via an incoming webhook."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        webhook_url = ctx.config.get("webhook_url")
        if not webhook_url or not str(webhook_url).strip():
            raise ValueError("discord target requires config.webhook_url")

        url = str(webhook_url).strip()
        results: list[DeliveryResult] = []
        for job in jobs:
            results.append(self._send_one(url, job))
        return results

    def _send_one(self, webhook_url: str, job: JobPosting) -> DeliveryResult:
        payload = self._payload(job)
        try:
            resp = self._client.post(webhook_url, json=payload)
            resp.raise_for_status()
            return DeliveryResult(external_id=job.external_id, status="sent")
        except httpx.HTTPError as exc:
            logger.warning("discord send failed for %s: %s", job.external_id, exc)
            return DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))

    @staticmethod
    def _payload(job: JobPosting) -> dict[str, Any]:
        title = job.title or "New job"
        if job.company:
            title = f"{title} @ {job.company}"

        description_parts: list[str] = []
        if job.company and job.title:
            description_parts.append(job.company)
        if job.location:
            description_parts.append(job.location)

        embed: dict[str, Any] = {
            "title": title,
            "color": _EMBED_COLOR,
        }
        if description_parts:
            embed["description"] = "\n".join(description_parts)
        if job.url:
            embed["url"] = job.url

        return {"embeds": [embed]}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
