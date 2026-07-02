import json

import httpx
import pytest

from app.scrapers.types import JobPosting
from app.summarizers import SummaryContext
from app.summarizers.adapters.llamacpp import LlamaCppSummarizer


class _Settings:
    llamacpp_base_url = "http://localhost:8080/v1"
    llamacpp_model = "local"
    llamacpp_api_key = ""


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Senior Python Engineer",
        company="ACME",
        location="Remote",
    )


def test_llamacpp_posts_chat_completion_without_api_key() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert "Authorization" not in request.headers
        assert str(request.url) == "http://localhost:8080/v1/chat/completions"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Strong Python match for your search."}}]},
        )

    summarizer = LlamaCppSummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    ctx = SummaryContext(search_name="Backend", filters={"keywords": "python"})

    blurbs = summarizer.summarize(ctx, [_job()])

    assert blurbs == ["Strong Python match for your search."]
    assert captured[0]["model"] == "local"
    assert captured[0]["messages"][0]["role"] == "system"


def test_llamacpp_sends_bearer_token_when_configured() -> None:
    class _WithKey(_Settings):
        llamacpp_api_key = "dev-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer dev-secret"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Match."}}]},
        )

    summarizer = LlamaCppSummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_WithKey(),
    )
    blurbs = summarizer.summarize(SummaryContext(), [_job()])
    assert blurbs == ["Match."]


def test_llamacpp_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="server down")

    summarizer = LlamaCppSummarizer(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )
    with pytest.raises(httpx.HTTPError):
        summarizer.summarize(SummaryContext(), [_job()])
