"""ntfy notifier.

Publishes one push per new job using ntfy's JSON publishing API (POST a JSON
body to the server root). JSON publishing avoids HTTP-header encoding pitfalls
with non-ASCII titles/messages.

Target config:
    {
      "server_url": "https://ntfy.sh",   # default
      "topic": "my-secret-topic",          # required
      "priority": "default",                # min|low|default|high|max
      "token": "tk_..."                     # optional, for protected topics
    }
"""

from typing import Any

import httpx

from app.core.logging import get_logger
from app.notifiers.base import Notifier, register_notifier
from app.notifiers.digest_format import digest_plain_body, digest_title
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting

logger = get_logger(__name__)

DEFAULT_SERVER_URL = "https://ntfy.sh"
_PRIORITY_MAP = {"min": 1, "low": 2, "default": 3, "high": 4, "max": 5}


@register_notifier("ntfy")
class NtfyNotifier(Notifier):
    """Send new jobs as ntfy push notifications."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        cfg = ctx.config
        topic = cfg.get("topic")
        if not topic:
            raise ValueError("ntfy target requires config.topic")
        server_url = str(cfg.get("server_url") or DEFAULT_SERVER_URL).rstrip("/")
        priority = _PRIORITY_MAP.get(str(cfg.get("priority", "default")), 3)
        headers = self._auth_headers(cfg)

        if ctx.digest:
            return self._send_digest(server_url, topic, priority, headers, ctx, jobs)

        results: list[DeliveryResult] = []
        for job in jobs:
            results.append(self._send_one(server_url, topic, priority, headers, job))
        return results

    def _send_digest(
        self,
        server_url: str,
        topic: str,
        priority: int,
        headers: dict[str, str],
        ctx: NotifyContext,
        jobs: list[JobPosting],
    ) -> list[DeliveryResult]:
        if not jobs:
            return []
        payload: dict[str, Any] = {
            "topic": topic,
            "title": digest_title(len(jobs), ctx.search_name),
            "message": digest_plain_body(jobs),
            "priority": priority,
            "tags": ["briefcase"],
        }
        try:
            resp = self._client.post(server_url, json=payload, headers=headers)
            resp.raise_for_status()
            return [DeliveryResult(external_id=job.external_id, status="sent") for job in jobs]
        except httpx.HTTPError as exc:
            logger.warning("ntfy digest send failed: %s", exc)
            return [
                DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))
                for job in jobs
            ]

    def _send_one(
        self,
        server_url: str,
        topic: str,
        priority: int,
        headers: dict[str, str],
        job: JobPosting,
    ) -> DeliveryResult:
        payload: dict[str, Any] = {
            "topic": topic,
            "title": self._title(job),
            "message": self._message(job),
            "priority": priority,
            "tags": ["briefcase"],
        }
        if job.url:
            payload["click"] = job.url
        try:
            resp = self._client.post(server_url, json=payload, headers=headers)
            resp.raise_for_status()
            return DeliveryResult(external_id=job.external_id, status="sent")
        except httpx.HTTPError as exc:
            logger.warning("ntfy send failed for %s: %s", job.external_id, exc)
            return DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))

    @staticmethod
    def _auth_headers(cfg: dict[str, Any]) -> dict[str, str]:
        token = cfg.get("token")
        return {"Authorization": f"Bearer {token}"} if token else {}

    @staticmethod
    def _title(job: JobPosting) -> str:
        return f"{job.title} @ {job.company}" if job.company else job.title

    @staticmethod
    def _message(job: JobPosting) -> str:
        parts = [p for p in (job.summary, job.location, job.url) if p]
        return "\n".join(parts) if parts else "New job posting"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
