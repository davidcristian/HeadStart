import json

import httpx

from app.resumes.adapters.gemini import GeminiResumeCurator
from app.resumes.types import ResumeCurationContext


class _Settings:
    gemini_api_key = "gemini-test-key"
    gemini_model = "gemini-2.0-flash"
    gemini_base_url = "https://generativelanguage.googleapis.com/v1beta"
    resume_curation_max_tokens = 1200


def _gemini_response(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}]},
    )


def test_gemini_resume_curator_sends_key_in_header_not_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gemini-test-key"
        assert "key=" not in str(request.url)
        return _gemini_response(json.dumps({"summary": "Seasoned backend engineer."}))

    curator = GeminiResumeCurator(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        settings=_Settings(),
    )

    curated = curator.curate(ResumeCurationContext(job_title="Engineer", company="ACME"))
    assert curated.summary == "Seasoned backend engineer."
