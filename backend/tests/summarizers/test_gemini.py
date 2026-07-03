import json

import httpx
import pytest

from app.scrapers.types import JobPosting
from app.summarizers import SummaryContext
from app.summarizers.adapters.gemini import GeminiSummarizer


class _Settings:
    gemini_api_key = "gemini-test-key"
    gemini_model = "gemini-2.0-flash"
    gemini_base_url = "https://generativelanguage.googleapis.com/v1beta"


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Senior Python Engineer",
        company="ACME",
        location="Remote",
    )


def test_gemini_posts_generate_content_and_returns_blurb() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert str(request.url).startswith(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        )
        assert request.headers["x-goog-api-key"] == "gemini-test-key"
        assert "key=" not in str(request.url)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Strong Python match for your search."}],
                            "role": "model",
                        }
                    }
                ]
            },
        )

    summarizer = GeminiSummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    ctx = SummaryContext(search_name="Backend", filters={"keywords": "python"})

    blurbs = summarizer.summarize(ctx, [_job()])

    assert blurbs == ["Strong Python match for your search."]
    assert captured[0]["systemInstruction"]["parts"][0]["text"]
    assert captured[0]["contents"][0]["role"] == "user"
    assert captured[0]["generationConfig"]["maxOutputTokens"] == 80


def test_gemini_requires_api_key() -> None:
    class _NoKey:
        gemini_api_key = ""
        gemini_model = "gemini-2.0-flash"
        gemini_base_url = "https://generativelanguage.googleapis.com/v1beta"

    summarizer = GeminiSummarizer(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        summarizer.summarize(SummaryContext(), [_job()])


def test_gemini_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    summarizer = GeminiSummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    with pytest.raises(httpx.HTTPError):
        summarizer.summarize(SummaryContext(), [_job()])


def test_gemini_close_behaviour() -> None:
    summarizer = GeminiSummarizer(settings=_Settings())
    summarizer.close()
    assert summarizer._client.is_closed

    client = httpx.Client()
    injected = GeminiSummarizer(client=client, settings=_Settings())
    injected.close()
    assert not client.is_closed
    client.close()
