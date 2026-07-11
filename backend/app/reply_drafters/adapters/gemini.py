"""Google Gemini reply drafter."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import extract_gemini_content, gemini_headers, gemini_url, llm_post
from app.core.config import settings as default_settings
from app.reply_drafters.base import ReplyDrafter, register_reply_drafter
from app.reply_drafters.prompts import SYSTEM_PROMPT, parse_reply_json, user_prompt
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult


@register_reply_drafter("gemini")
class GeminiReplyDrafter(ReplyDrafter):
    """Draft recruiter replies with Google Gemini."""

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
        api_key = str(getattr(self._settings, "gemini_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("gemini reply drafter requires GEMINI_API_KEY")
        url = gemini_url(str(self._settings.gemini_base_url), str(self._settings.gemini_model))
        headers = gemini_headers(api_key)
        max_tokens = int(getattr(self._settings, "email_draft_max_tokens", 600))
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt(ctx)}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": max_tokens,
            },
        }
        resp = llm_post(self._client, url, json=payload, headers=headers)
        resp.raise_for_status()
        return parse_reply_json(extract_gemini_content(resp.json()))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
