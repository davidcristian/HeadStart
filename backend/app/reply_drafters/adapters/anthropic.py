"""Anthropic Claude reply drafter."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_anthropic_content
from app.core.config import settings as default_settings
from app.reply_drafters.base import ReplyDrafter, register_reply_drafter
from app.reply_drafters.prompts import SYSTEM_PROMPT, parse_reply_json, user_prompt
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult


@register_reply_drafter("anthropic")
class AnthropicReplyDrafter(ReplyDrafter):
    """Draft recruiter replies with Anthropic Claude."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=45.0)

    def draft(self, ctx: ReplyDraftContext) -> ReplyDraftResult:
        api_key = str(getattr(self._settings, "anthropic_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("anthropic reply drafter requires ANTHROPIC_API_KEY")
        base_url = str(self._settings.anthropic_base_url).rstrip("/")
        model = str(self._settings.anthropic_model)
        api_version = str(self._settings.anthropic_api_version)
        url = f"{base_url}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": api_version,
        }
        max_tokens = int(getattr(self._settings, "email_draft_max_tokens", 600))
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt(ctx)}],
        }
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return parse_reply_json(extract_anthropic_content(resp.json()))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
