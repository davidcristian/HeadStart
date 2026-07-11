"""Tests for the OpenAI / Anthropic / llama.cpp reply-drafter LLM adapters."""

import json

import httpx
import pytest

from app.reply_drafters.adapters.anthropic import AnthropicReplyDrafter
from app.reply_drafters.adapters.llamacpp import LlamaCppReplyDrafter
from app.reply_drafters.adapters.openai import OpenAIReplyDrafter
from app.reply_drafters.types import ReplyDraftContext
from app.schemas.profile import ProfileData


class _OpenAISettings:
    openai_api_key = "sk-test"
    openai_model = "gpt-4o-mini"
    openai_base_url = "https://api.openai.fixture.test/v1"
    email_draft_max_tokens = 600


class _AnthropicSettings:
    anthropic_api_key = "sk-ant-test"
    anthropic_model = "claude-3-5-haiku-latest"
    anthropic_base_url = "https://api.anthropic.fixture.test/v1"
    anthropic_api_version = "2023-06-01"
    email_draft_max_tokens = 600


class _LlamaCppSettings:
    llamacpp_base_url = "http://localhost:8080/v1"
    llamacpp_model = "local"
    llamacpp_api_key = ""
    email_draft_max_tokens = 600


def _ctx() -> ReplyDraftContext:
    return ReplyDraftContext(profile=ProfileData())


_REPLY = json.dumps({"subject": "Re: hi", "body": "Thanks!", "notes": ""})


def _openai_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def _anthropic_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def test_openai_posts_and_parses_reply() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert str(request.url) == "https://api.openai.fixture.test/v1/chat/completions"
        return _openai_response(_REPLY)

    drafter = OpenAIReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    result = drafter.draft(_ctx())
    assert result.body == "Thanks!"
    assert captured[0]["max_tokens"] == 600


def test_openai_requires_api_key() -> None:
    class _NoKey(_OpenAISettings):
        openai_api_key = ""

    drafter = OpenAIReplyDrafter(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        drafter.draft(_ctx())


def test_openai_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    drafter = OpenAIReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    with pytest.raises(httpx.HTTPError):
        drafter.draft(_ctx())


def test_openai_close_behaviour() -> None:
    drafter = OpenAIReplyDrafter(settings=_OpenAISettings())
    drafter.close()
    assert drafter._client.is_closed

    client = httpx.Client()
    injected = OpenAIReplyDrafter(client=client, settings=_OpenAISettings())
    injected.close()
    assert not client.is_closed
    client.close()


def test_anthropic_posts_and_parses_reply() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["x-api-key"] == "sk-ant-test"
        assert str(request.url) == "https://api.anthropic.fixture.test/v1/messages"
        return _anthropic_response(_REPLY)

    drafter = AnthropicReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    assert drafter.draft(_ctx()).body == "Thanks!"
    assert captured[0]["system"]


def test_anthropic_requires_api_key() -> None:
    class _NoKey(_AnthropicSettings):
        anthropic_api_key = ""

    drafter = AnthropicReplyDrafter(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        drafter.draft(_ctx())


def test_anthropic_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    drafter = AnthropicReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        drafter.draft(_ctx())


def test_anthropic_close_behaviour() -> None:
    drafter = AnthropicReplyDrafter(settings=_AnthropicSettings())
    drafter.close()
    assert drafter._client.is_closed

    client = httpx.Client()
    injected = AnthropicReplyDrafter(client=client, settings=_AnthropicSettings())
    injected.close()
    assert not client.is_closed
    client.close()


def test_llamacpp_posts_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        assert str(request.url) == "http://localhost:8080/v1/chat/completions"
        return _openai_response(_REPLY)

    drafter = LlamaCppReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    assert drafter.draft(_ctx()).body == "Thanks!"


def test_llamacpp_sends_bearer_when_key_set() -> None:
    class _WithKey(_LlamaCppSettings):
        llamacpp_api_key = "dev-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer dev-secret"
        return _openai_response(_REPLY)

    drafter = LlamaCppReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_WithKey(),
    )
    assert drafter.draft(_ctx()).body == "Thanks!"


def test_llamacpp_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    drafter = LlamaCppReplyDrafter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        drafter.draft(_ctx())


def test_llamacpp_close_behaviour() -> None:
    drafter = LlamaCppReplyDrafter(settings=_LlamaCppSettings())
    drafter.close()
    assert drafter._client.is_closed

    client = httpx.Client()
    injected = LlamaCppReplyDrafter(client=client, settings=_LlamaCppSettings())
    injected.close()
    assert not client.is_closed
    client.close()
