"""Tests for the OpenAI / Anthropic / llama.cpp resume-curator LLM adapters."""

import json

import httpx
import pytest

from app.resumes.adapters.anthropic import AnthropicResumeCurator
from app.resumes.adapters.gemini import GeminiResumeCurator
from app.resumes.adapters.llamacpp import LlamaCppResumeCurator
from app.resumes.adapters.openai import OpenAIResumeCurator
from app.resumes.types import ResumeCurationContext


class _GeminiSettings:
    gemini_api_key = "gemini-test-key"
    gemini_model = "gemini-2.0-flash"
    gemini_base_url = "https://generativelanguage.googleapis.fixture.test/v1beta"
    resume_curation_max_tokens = 1200


class _OpenAISettings:
    openai_api_key = "sk-test"
    openai_model = "gpt-4o-mini"
    openai_base_url = "https://api.openai.fixture.test/v1"
    resume_curation_max_tokens = 1200


class _AnthropicSettings:
    anthropic_api_key = "sk-ant-test"
    anthropic_model = "claude-3-5-haiku-latest"
    anthropic_base_url = "https://api.anthropic.fixture.test/v1"
    anthropic_api_version = "2023-06-01"
    resume_curation_max_tokens = 1200


class _LlamaCppSettings:
    llamacpp_base_url = "http://localhost:8080/v1"
    llamacpp_model = "local"
    llamacpp_api_key = ""
    resume_curation_max_tokens = 1200


def _ctx() -> ResumeCurationContext:
    return ResumeCurationContext(job_title="Engineer", company="ACME")


_CURATED = json.dumps({"summary": "Seasoned backend engineer."})


def _openai_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def _anthropic_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def test_openai_posts_and_parses_fields() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert str(request.url) == "https://api.openai.fixture.test/v1/chat/completions"
        return _openai_response(_CURATED)

    curator = OpenAIResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    curated = curator.curate(_ctx())
    assert curated.summary == "Seasoned backend engineer."
    assert captured[0]["max_tokens"] == 1200
    assert captured[0]["response_format"] == {"type": "json_object"}


def test_openai_requires_api_key() -> None:
    class _NoKey(_OpenAISettings):
        openai_api_key = ""

    curator = OpenAIResumeCurator(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        curator.curate(_ctx())


def test_openai_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    curator = OpenAIResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_OpenAISettings(),
    )
    with pytest.raises(httpx.HTTPError):
        curator.curate(_ctx())


def test_openai_close_behaviour() -> None:
    curator = OpenAIResumeCurator(settings=_OpenAISettings())
    curator.close()
    assert curator._client.is_closed

    client = httpx.Client()
    injected = OpenAIResumeCurator(client=client, settings=_OpenAISettings())
    injected.close()
    assert not client.is_closed
    client.close()


def test_anthropic_posts_and_parses_fields() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["x-api-key"] == "sk-ant-test"
        assert request.headers["content-type"] == "application/json"
        assert str(request.url) == "https://api.anthropic.fixture.test/v1/messages"
        return _anthropic_response(_CURATED)

    curator = AnthropicResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    assert curator.curate(_ctx()).summary == "Seasoned backend engineer."
    assert captured[0]["system"]


def test_anthropic_requires_api_key() -> None:
    class _NoKey(_AnthropicSettings):
        anthropic_api_key = ""

    curator = AnthropicResumeCurator(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        curator.curate(_ctx())


def test_anthropic_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    curator = AnthropicResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_AnthropicSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        curator.curate(_ctx())


def test_anthropic_close_behaviour() -> None:
    curator = AnthropicResumeCurator(settings=_AnthropicSettings())
    curator.close()
    assert curator._client.is_closed

    client = httpx.Client()
    injected = AnthropicResumeCurator(client=client, settings=_AnthropicSettings())
    injected.close()
    assert not client.is_closed
    client.close()


def test_llamacpp_posts_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        assert str(request.url) == "http://localhost:8080/v1/chat/completions"
        return _openai_response(_CURATED)

    curator = LlamaCppResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    assert curator.curate(_ctx()).summary == "Seasoned backend engineer."


def test_llamacpp_sends_bearer_when_key_set() -> None:
    class _WithKey(_LlamaCppSettings):
        llamacpp_api_key = "dev-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer dev-secret"
        return _openai_response(_CURATED)

    curator = LlamaCppResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_WithKey(),
    )
    assert curator.curate(_ctx()).summary == "Seasoned backend engineer."


def test_llamacpp_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    curator = LlamaCppResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_LlamaCppSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        curator.curate(_ctx())


def test_llamacpp_close_behaviour() -> None:
    curator = LlamaCppResumeCurator(settings=_LlamaCppSettings())
    curator.close()
    assert curator._client.is_closed

    client = httpx.Client()
    injected = LlamaCppResumeCurator(client=client, settings=_LlamaCppSettings())
    injected.close()
    assert not client.is_closed
    client.close()


def test_gemini_requires_api_key() -> None:
    class _NoKey(_GeminiSettings):
        gemini_api_key = ""

    curator = GeminiResumeCurator(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        curator.curate(_ctx())


def test_gemini_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    curator = GeminiResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_GeminiSettings(),
    )
    with pytest.raises(httpx.HTTPError):
        curator.curate(_ctx())


def test_gemini_close_behaviour() -> None:
    curator = GeminiResumeCurator(settings=_GeminiSettings())
    curator.close()
    assert curator._client.is_closed

    client = httpx.Client()
    injected = GeminiResumeCurator(client=client, settings=_GeminiSettings())
    injected.close()
    assert not client.is_closed
    client.close()
