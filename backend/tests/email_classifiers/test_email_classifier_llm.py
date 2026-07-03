"""Tests for the OpenAI / Anthropic / llama.cpp email-classifier LLM adapters."""

import json

import httpx
import pytest

from app.email_classifiers.adapters.anthropic import AnthropicEmailClassifier
from app.email_classifiers.adapters.llamacpp import LlamaCppEmailClassifier
from app.email_classifiers.adapters.openai import OpenAIEmailClassifier
from app.email_classifiers.types import EmailClassifyContext
from app.inbox.types import InboxMessage


class _OpenAISettings:
    openai_api_key = "sk-test"
    openai_model = "gpt-4o-mini"
    openai_base_url = "https://api.openai.com/v1"
    email_classify_max_tokens = 256


class _AnthropicSettings:
    anthropic_api_key = "sk-ant-test"
    anthropic_model = "claude-3-5-haiku-latest"
    anthropic_base_url = "https://api.anthropic.com/v1"
    anthropic_api_version = "2023-06-01"
    email_classify_max_tokens = 256


class _LlamaCppSettings:
    llamacpp_base_url = "http://localhost:8080/v1"
    llamacpp_model = "local"
    llamacpp_api_key = ""
    email_classify_max_tokens = 256


def _ctx() -> EmailClassifyContext:
    return EmailClassifyContext(
        message=InboxMessage(uid=1, from_addr="r@acme.com", subject="Hi", body_text="Thanks."),
    )


_LABEL = json.dumps({"label": "general", "confidence": 0.9, "reason": "ok"})


def _openai_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def _anthropic_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def test_openai_posts_and_parses_label() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        return _openai_response(_LABEL)

    classifier = OpenAIEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    assert classifier.classify(_ctx()).label == "general"
    assert captured[0]["max_tokens"] == 256


def test_openai_requires_api_key() -> None:
    class _NoKey(_OpenAISettings):
        openai_api_key = ""

    classifier = OpenAIEmailClassifier(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        classifier.classify(_ctx())


def test_openai_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    classifier = OpenAIEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    with pytest.raises(httpx.HTTPError):
        classifier.classify(_ctx())


def test_openai_close_behaviour() -> None:
    classifier = OpenAIEmailClassifier(settings=_OpenAISettings())
    classifier.close()
    assert classifier._client.is_closed

    client = httpx.Client()
    injected = OpenAIEmailClassifier(client=client, settings=_OpenAISettings())
    injected.close()
    assert not client.is_closed
    client.close()


def test_anthropic_posts_and_parses_label() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["x-api-key"] == "sk-ant-test"
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        return _anthropic_response(_LABEL)

    classifier = AnthropicEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    assert classifier.classify(_ctx()).label == "general"
    assert captured[0]["system"]


def test_anthropic_requires_api_key() -> None:
    class _NoKey(_AnthropicSettings):
        anthropic_api_key = ""

    classifier = AnthropicEmailClassifier(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        classifier.classify(_ctx())


def test_anthropic_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    classifier = AnthropicEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        classifier.classify(_ctx())


def test_anthropic_close_behaviour() -> None:
    classifier = AnthropicEmailClassifier(settings=_AnthropicSettings())
    classifier.close()
    assert classifier._client.is_closed

    client = httpx.Client()
    injected = AnthropicEmailClassifier(client=client, settings=_AnthropicSettings())
    injected.close()
    assert not client.is_closed
    client.close()


def test_llamacpp_posts_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        assert str(request.url) == "http://localhost:8080/v1/chat/completions"
        return _openai_response(_LABEL)

    classifier = LlamaCppEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    assert classifier.classify(_ctx()).label == "general"


def test_llamacpp_sends_bearer_when_key_set() -> None:
    class _WithKey(_LlamaCppSettings):
        llamacpp_api_key = "dev-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer dev-secret"
        return _openai_response(_LABEL)

    classifier = LlamaCppEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_WithKey(),
    )
    assert classifier.classify(_ctx()).label == "general"


def test_llamacpp_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    classifier = LlamaCppEmailClassifier(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        classifier.classify(_ctx())


def test_llamacpp_close_behaviour() -> None:
    classifier = LlamaCppEmailClassifier(settings=_LlamaCppSettings())
    classifier.close()
    assert classifier._client.is_closed

    client = httpx.Client()
    injected = LlamaCppEmailClassifier(client=client, settings=_LlamaCppSettings())
    injected.close()
    assert not client.is_closed
    client.close()
