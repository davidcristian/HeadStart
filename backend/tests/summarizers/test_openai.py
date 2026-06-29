import json

import httpx
import pytest

from app.scrapers.types import JobPosting
from app.summarizers import SummaryContext
from app.summarizers.adapters.openai import OpenAISummarizer


class _Settings:
    openai_api_key = "sk-test"
    openai_model = "gpt-4o-mini"
    openai_base_url = "https://api.openai.com/v1"


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Senior Python Engineer",
        company="ACME",
        location="Remote",
    )


def test_openai_posts_chat_completion_and_returns_blurb() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Strong Python match for your search."}}]},
        )

    summarizer = OpenAISummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    ctx = SummaryContext(search_name="Backend", filters={"keywords": "python"})

    blurbs = summarizer.summarize(ctx, [_job()])

    assert blurbs == ["Strong Python match for your search."]
    assert captured[0]["model"] == "gpt-4o-mini"
    assert captured[0]["messages"][0]["role"] == "system"


def test_openai_requires_api_key() -> None:
    class _NoKey:
        openai_api_key = ""
        openai_model = "gpt-4o-mini"
        openai_base_url = "https://api.openai.com/v1"

    summarizer = OpenAISummarizer(client=httpx.Client(), settings=_NoKey())
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        summarizer.summarize(SummaryContext(), [_job()])


def test_openai_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    summarizer = OpenAISummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    with pytest.raises(httpx.HTTPError):
        summarizer.summarize(SummaryContext(), [_job()])
