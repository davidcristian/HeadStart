"""llama.cpp local email classifier (dev-only)."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.llm_common import auth_headers, extract_openai_content
from app.core.config import settings as default_settings
from app.email_classifiers.base import EmailClassifier, register_email_classifier
from app.email_classifiers.prompts import SYSTEM_PROMPT, parse_classification_json, user_prompt
from app.email_classifiers.types import EmailClassificationResult, EmailClassifyContext


@register_email_classifier("llamacpp")
class LlamaCppEmailClassifier(EmailClassifier):
    """Classify recruiter email with a local llama.cpp OpenAI-compatible server."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        settings: Any = default_settings,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=90.0)

    def classify(self, ctx: EmailClassifyContext) -> EmailClassificationResult:
        base_url = str(self._settings.llamacpp_base_url).rstrip("/")
        model = str(self._settings.llamacpp_model)
        url = f"{base_url}/chat/completions"
        headers = auth_headers(str(getattr(self._settings, "llamacpp_api_key", "") or ""))
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
