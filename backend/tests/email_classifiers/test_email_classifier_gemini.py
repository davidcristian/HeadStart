import json

import httpx
import pytest

from app.email_classifiers.adapters.gemini import GeminiEmailClassifier
from app.email_classifiers.types import EmailClassifyContext
from app.inbox.types import InboxMessage


class _Settings:
    gemini_api_key = "gemini-test-key"
    gemini_model = "gemini-2.0-flash"
    gemini_base_url = "https://generativelanguage.googleapis.fixture.test/v1beta"
    email_classify_max_tokens = 256


def _ctx() -> EmailClassifyContext:
    return EmailClassifyContext(
        message=InboxMessage(
            uid=1,
            from_addr="recruiter@acme.com",
            subject="Hello",
            body_text="Thanks for applying.",
        )
    )


def test_gemini_email_classifier_sends_key_in_header_and_quotes_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gemini-test-key"
        assert "key=" not in str(request.url)
        assert str(request.url).endswith("/models/gemini-2.0-flash:generateContent")
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {"label": "general", "confidence": 0.9, "reason": "ok"}
                                    )
                                }
                            ],
                            "role": "model",
                        }
                    }
                ]
            },
        )

    classifier = GeminiEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )

    result = classifier.classify(_ctx())
    assert result.label == "general"


def test_gemini_email_classifier_requires_api_key() -> None:
    class _NoKey(_Settings):
        gemini_api_key = ""

    classifier = GeminiEmailClassifier(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        classifier.classify(_ctx())


def test_gemini_email_classifier_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    classifier = GeminiEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    with pytest.raises(httpx.HTTPError):
        classifier.classify(_ctx())


def test_gemini_email_classifier_close_behaviour() -> None:
    classifier = GeminiEmailClassifier(settings=_Settings())
    classifier.close()
    assert classifier._client.is_closed

    client = httpx.Client()
    injected = GeminiEmailClassifier(client=client, settings=_Settings())
    injected.close()
    assert not client.is_closed
    client.close()
