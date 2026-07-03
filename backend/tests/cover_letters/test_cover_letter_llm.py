"""Tests for the OpenAI / Anthropic / llama.cpp cover-letter LLM adapters."""

import json

import httpx
import pytest

from app.cover_letters.adapters.anthropic import AnthropicCoverLetterGenerator
from app.cover_letters.adapters.llamacpp import LlamaCppCoverLetterGenerator
from app.cover_letters.adapters.openai import OpenAICoverLetterGenerator
from app.cover_letters.types import CoverLetterContext


class _OpenAISettings:
    openai_api_key = "sk-test"
    openai_model = "gpt-4o-mini"
    openai_base_url = "https://api.openai.com/v1"
    cover_letter_max_tokens = 900


class _AnthropicSettings:
    anthropic_api_key = "sk-ant-test"
    anthropic_model = "claude-3-5-haiku-latest"
    anthropic_base_url = "https://api.anthropic.com/v1"
    anthropic_api_version = "2023-06-01"
    cover_letter_max_tokens = 900


class _LlamaCppSettings:
    llamacpp_base_url = "http://localhost:8080/v1"
    llamacpp_model = "local"
    llamacpp_api_key = ""
    cover_letter_max_tokens = 900


def _ctx() -> CoverLetterContext:
    return CoverLetterContext(job_title="Engineer", company="ACME")


def _openai_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def _anthropic_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def test_openai_posts_and_returns_letter() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        return _openai_response("Dear ACME team, ...")

    generator = OpenAICoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    assert generator.generate(_ctx()) == "Dear ACME team, ..."
    assert captured[0]["max_tokens"] == 900
    assert captured[0]["messages"][0]["role"] == "system"


def test_openai_requires_api_key() -> None:
    class _NoKey(_OpenAISettings):
        openai_api_key = ""

    generator = OpenAICoverLetterGenerator(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        generator.generate(_ctx())


def test_openai_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    generator = OpenAICoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    with pytest.raises(httpx.HTTPError):
        generator.generate(_ctx())


def test_openai_close_closes_owned_client() -> None:
    generator = OpenAICoverLetterGenerator(settings=_OpenAISettings())
    generator.close()
    assert generator._client.is_closed


def test_openai_close_leaves_injected_client_open() -> None:
    client = httpx.Client()
    generator = OpenAICoverLetterGenerator(client=client, settings=_OpenAISettings())
    generator.close()
    assert not client.is_closed
    client.close()


def test_anthropic_posts_and_returns_letter() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["x-api-key"] == "sk-ant-test"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        return _anthropic_response("Dear ACME team, ...")

    generator = AnthropicCoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    assert generator.generate(_ctx()) == "Dear ACME team, ..."
    assert captured[0]["system"]
    assert captured[0]["messages"][0]["role"] == "user"


def test_anthropic_requires_api_key() -> None:
    class _NoKey(_AnthropicSettings):
        anthropic_api_key = ""

    generator = AnthropicCoverLetterGenerator(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        generator.generate(_ctx())


def test_anthropic_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    generator = AnthropicCoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        generator.generate(_ctx())


def test_anthropic_close_closes_owned_client() -> None:
    generator = AnthropicCoverLetterGenerator(settings=_AnthropicSettings())
    generator.close()
    assert generator._client.is_closed


def test_anthropic_close_leaves_injected_client_open() -> None:
    client = httpx.Client()
    generator = AnthropicCoverLetterGenerator(client=client, settings=_AnthropicSettings())
    generator.close()
    assert not client.is_closed
    client.close()


def test_llamacpp_posts_without_key() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert "Authorization" not in request.headers
        assert str(request.url) == "http://localhost:8080/v1/chat/completions"
        return _openai_response("Dear ACME team, ...")

    generator = LlamaCppCoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    assert generator.generate(_ctx()) == "Dear ACME team, ..."
    assert captured[0]["model"] == "local"


def test_llamacpp_sends_bearer_when_key_set() -> None:
    class _WithKey(_LlamaCppSettings):
        llamacpp_api_key = "dev-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer dev-secret"
        return _openai_response("ok")

    generator = LlamaCppCoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_WithKey(),
    )
    assert generator.generate(_ctx()) == "ok"


def test_llamacpp_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    generator = LlamaCppCoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        generator.generate(_ctx())


def test_llamacpp_close_closes_owned_client() -> None:
    generator = LlamaCppCoverLetterGenerator(settings=_LlamaCppSettings())
    generator.close()
    assert generator._client.is_closed


def test_llamacpp_close_leaves_injected_client_open() -> None:
    client = httpx.Client()
    generator = LlamaCppCoverLetterGenerator(client=client, settings=_LlamaCppSettings())
    generator.close()
    assert not client.is_closed
    client.close()
