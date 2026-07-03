"""OpenAI-backed email classifier."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings as default_settings
from app.email_classifiers.adapters.llm_common import extract_openai_content
from app.email_classifiers.base import EmailClassifier, register_email_classifier
from app.email_classifiers.prompts import SYSTEM_PROMPT, parse_classification_json, user_prompt
from app.email_classifiers.types import EmailClassificationResult, EmailClassifyContext


@register_email_classifier("openai")
class OpenAIEmailClassifier(EmailClassifier):
    """Classify recruiter email with an OpenAI-compatible chat model."""

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
        api_key = str(getattr(self._settings, "openai_api_key", "") or "").strip()
        if not api_key:
            raise ValueError("openai email classifier requires OPENAI_API_KEY")
        base_url = str(self._settings.openai_base_url).rstrip("/")
        model = str(self._settings.openai_model)
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        max_tokens = int(getattr(self._settings, "email_classify_max_tokens", 256))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(ctx)},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        resp = self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return parse_classification_json(extract_openai_content(resp.json()))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
