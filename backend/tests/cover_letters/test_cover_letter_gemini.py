import httpx

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
