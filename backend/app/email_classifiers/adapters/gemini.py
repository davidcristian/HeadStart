"""Gemini-backed email classifier."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings as default_settings
from app.email_classifiers.adapters.llm_common import extract_gemini_content
from app.email_classifiers.base import EmailClassifier, register_email_classifier
from app.email_classifiers.prompts import SYSTEM_PROMPT, parse_classification_json, user_prompt
from app.email_classifiers.types import EmailClassificationResult, EmailClassifyContext


@register_email_classifier("gemini")
class GeminiEmailClassifier(EmailClassifier):
    """Classify recruiter email with the Gemini API."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=45.0)

    def classify(self, ctx: EmailClassifyContext) -> EmailClassificationResult:
        api_key = str(getattr(self._settings, "gemini_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("gemini email classifier requires GEMINI_API_KEY")
        model = str(self._settings.gemini_model)
        base_url = str(self._settings.gemini_base_url).rstrip("/")
        url = f"{base_url}/models/{model}:generateContent"
        headers = {"x-goog-api-key": api_key}
        max_tokens = int(getattr(self._settings, "email_classify_max_tokens", 256))
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt(ctx)}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": max_tokens,
            },
        }
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return parse_classification_json(extract_gemini_content(resp.json()))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
