"""Telegram Bot API notifier.

Posts one message per new job via the Telegram Bot API. Create a bot with
@BotFather, start a chat with it (or add it to a group), then use your chat id.

Target config:
    {
      "bot_token": "123456:ABC-DEF...",  # required
      "chat_id": "123456789"             # required (user, group, or channel id)
    }
"""

import html
from typing import Any

import httpx

from app.core.logging import get_logger
from app.notifiers.base import Notifier, register_notifier
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org"


@register_notifier("telegram")
class TelegramNotifier(Notifier):
    """Send new jobs as Telegram messages via the Bot API."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=15.0)

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        bot_token = ctx.config.get("bot_token")
        chat_id = ctx.config.get("chat_id")
        if not bot_token or not str(bot_token).strip():
            raise ValueError("telegram target requires config.bot_token")
        if chat_id is None or not str(chat_id).strip():
            raise ValueError("telegram target requires config.chat_id")

        token = str(bot_token).strip()
        chat = str(chat_id).strip()
        url = f"{_TELEGRAM_API}/bot{token}/sendMessage"

        results: list[DeliveryResult] = []
        for job in jobs:
            results.append(self._send_one(url, chat, job))
        return results

    def _send_one(self, api_url: str, chat_id: str, job: JobPosting) -> DeliveryResult:
        payload = self._payload(chat_id, job)
        try:
            resp = self._client.post(api_url, json=payload)
            resp.raise_for_status()
            return DeliveryResult(external_id=job.external_id, status="sent")
        except httpx.HTTPError as exc:
            logger.warning("telegram send failed for %s: %s", job.external_id, exc)
            return DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))

    @staticmethod
    def _payload(chat_id: str, job: JobPosting) -> dict[str, Any]:
        return {
            "chat_id": chat_id,
            "text": TelegramNotifier._text(job),
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

    @staticmethod
    def _text(job: JobPosting) -> str:
        title = html.escape(job.title) if job.title else "New job"
        headline = f"<b>{title}</b>"
        if job.company:
            headline = f"{headline} @ {html.escape(job.company)}"

        lines = [headline]
        if job.location:
            lines.append(html.escape(job.location))
        if job.url:
            safe_url = html.escape(job.url, quote=True)
            lines.append(f'<a href="{safe_url}">Apply</a>')
        return "\n".join(lines)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
