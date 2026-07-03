import httpx

from app.notifiers import NotifyContext
from app.notifiers.adapters.ntfy import NtfyNotifier
from app.notifiers.digest_format import (
    digest_blocks,
    digest_plain_body,
    digest_text_lines,
    digest_title,
    job_headline,
)
from app.scrapers.types import JobPosting


def _job(external_id: str) -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url=f"https://careers.example/jobs/{external_id}",
    )


def test_ntfy_digest_posts_single_batched_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="ntfy",
        config={"topic": "secret"},
        digest=True,
        search_name="Backend roles",
    )

    results = notifier.send(ctx, [_job("1"), _job("2")])

    assert len(results) == 2
    assert all(r.status == "sent" for r in results)
    assert len(captured) == 1
    body = captured[0]
    assert body["title"] == "2 new jobs — Backend roles"
    assert "Software Engineer @ Google" in body["message"]
    assert "https://careers.example/jobs/1" in body["message"]


def test_job_headline_without_company_uses_title_only() -> None:
    assert job_headline(JobPosting(external_id="1", title="Engineer")) == "Engineer"
    assert job_headline(JobPosting(external_id="1", title="")) == "New job"


def test_digest_title_without_search_name_and_singular() -> None:
    assert digest_title(1) == "1 new job"
    assert digest_title(3) == "3 new jobs"


def test_digest_blocks_omit_location_when_absent() -> None:
    blocks = digest_blocks([JobPosting(external_id="1", title="Eng", company="ACME")])
    assert blocks[0].headline == "Eng @ ACME"


def test_digest_text_lines_omit_summary_and_url() -> None:
    lines = digest_text_lines([JobPosting(external_id="1", title="Eng", company="ACME")])
    assert lines == ["Eng @ ACME"]


def test_digest_text_lines_include_summary_and_url() -> None:
    job = JobPosting(
        external_id="1",
        title="Eng",
        company="ACME",
        location="Berlin",
        url="https://x/1",
        summary="great match",
    )
    (line,) = digest_text_lines([job])
    assert "Eng @ ACME (Berlin)" in line
    assert "great match" in line
    assert "https://x/1" in line


def test_digest_plain_body_joins_blocks() -> None:
    jobs = [
        JobPosting(external_id="1", title="A", company="X"),
        JobPosting(external_id="2", title="B", company="Y"),
    ]
    body = digest_plain_body(jobs)
    assert "A @ X" in body
    assert "B @ Y" in body
