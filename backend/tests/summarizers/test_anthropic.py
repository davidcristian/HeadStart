import json

import httpx
import pytest

from app.scrapers.types import JobPosting
from app.summarizers import SummaryContext
from app.summarizers.adapters.anthropic import AnthropicSummarizer


class _Settings:
    anthropic_api_key = "sk-ant-test"
    anthropic_model = "claude-3-5-haiku-latest"
    anthropic_base_url = "https://api.anthropic.com/v1"
    anthropic_api_version = "2023-06-01"


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Senior Python Engineer",
        company="ACME",
        location="Remote",
    )


def test_anthropic_posts_messages_and_returns_blurb() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["x-api-key"] == "sk-ant-test"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "Strong Python match for your search."}]},
        )

    summarizer = AnthropicSummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    ctx = SummaryContext(search_name="Backend", filters={"keywords": "python"})

    blurbs = summarizer.summarize(ctx, [_job()])

    assert blurbs == ["Strong Python match for your search."]
    assert captured[0]["model"] == "claude-3-5-haiku-latest"
    assert captured[0]["system"]
    assert captured[0]["messages"][0]["role"] == "user"
    assert captured[0]["max_tokens"] == 80


def test_anthropic_requires_api_key() -> None:
    class _NoKey:
        anthropic_api_key = ""
        anthropic_model = "claude-3-5-haiku-latest"
        anthropic_base_url = "https://api.anthropic.com/v1"
        anthropic_api_version = "2023-06-01"

    summarizer = AnthropicSummarizer(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        summarizer.summarize(SummaryContext(), [_job()])


def test_anthropic_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    summarizer = AnthropicSummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    with pytest.raises(httpx.HTTPError):
        summarizer.summarize(SummaryContext(), [_job()])
