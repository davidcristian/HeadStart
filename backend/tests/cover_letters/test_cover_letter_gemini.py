import httpx
import pytest

from app.cover_letters.adapters.gemini import GeminiCoverLetterGenerator
from app.cover_letters.types import CoverLetterContext


class _Settings:
    gemini_api_key = "gemini-test-key"
    gemini_model = "gemini-2.0-flash"
    gemini_base_url = "https://generativelanguage.googleapis.com/v1beta"
    cover_letter_max_tokens = 900


def _gemini_response(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}]},
    )


def test_gemini_cover_letter_sends_key_in_header_not_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gemini-test-key"
        assert "key=" not in str(request.url)
        return _gemini_response("Dear hiring team, I am excited to apply.")

    generator = GeminiCoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )

    assert (
        generator.generate(CoverLetterContext(job_title="Engineer", company="ACME"))
        == "Dear hiring team, I am excited to apply."
    )


def test_gemini_cover_letter_requires_api_key() -> None:
    class _NoKey(_Settings):
        gemini_api_key = ""

    generator = GeminiCoverLetterGenerator(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        generator.generate(CoverLetterContext(job_title="Engineer", company="ACME"))


def test_gemini_cover_letter_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    generator = GeminiCoverLetterGenerator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    with pytest.raises(httpx.HTTPError):
        generator.generate(CoverLetterContext(job_title="Engineer", company="ACME"))


def test_gemini_cover_letter_close_closes_owned_client() -> None:
    generator = GeminiCoverLetterGenerator(settings=_Settings())
    generator.close()
    assert generator._client.is_closed


def test_gemini_cover_letter_close_leaves_injected_client_open() -> None:
    client = httpx.Client()
    generator = GeminiCoverLetterGenerator(client=client, settings=_Settings())
    generator.close()
    assert not client.is_closed
    client.close()
