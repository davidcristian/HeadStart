"""OpenAI-backed reply drafter."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_openai_content, llm_post
from app.core.config import settings as default_settings
from app.reply_drafters.base import ReplyDrafter, register_reply_drafter
from app.reply_drafters.prompts import SYSTEM_PROMPT, parse_reply_json, user_prompt
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult


@register_reply_drafter("openai")
class OpenAIReplyDrafter(ReplyDrafter):
    """Draft recruiter replies with an OpenAI-compatible chat model."""

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
        api_key = str(getattr(self._settings, "openai_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("openai reply drafter requires OPENAI_API_KEY")
        base_url = str(self._settings.openai_base_url).rstrip("/")
        model = str(self._settings.openai_model)
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        max_tokens = int(getattr(self._settings, "email_draft_max_tokens", 600))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(ctx)},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        resp = llm_post(self._client, url, json=payload, headers=headers)
        resp.raise_for_status()
        return parse_reply_json(extract_openai_content(resp.json()))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
