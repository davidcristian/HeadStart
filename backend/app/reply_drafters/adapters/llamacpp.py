"""llama.cpp local reply drafter (dev-only)."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import auth_headers, extract_openai_content
from app.core.config import settings as default_settings
from app.reply_drafters.base import ReplyDrafter, register_reply_drafter
from app.reply_drafters.prompts import SYSTEM_PROMPT, parse_reply_json, user_prompt
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult


@register_reply_drafter("llamacpp")
class LlamaCppReplyDrafter(ReplyDrafter):
    """Draft recruiter replies with a local llama.cpp OpenAI-compatible server."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=90.0)

    def draft(self, ctx: ReplyDraftContext) -> ReplyDraftResult:
        base_url = str(self._settings.llamacpp_base_url).rstrip("/")
        model = str(self._settings.llamacpp_model)
        url = f"{base_url}/chat/completions"
        headers = auth_headers(str(getattr(self._settings, "llamacpp_api_key", "") or ""))
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
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return parse_reply_json(extract_openai_content(resp.json()))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
