"""Summarizer prompt builder coverage."""

from app.scrapers.types import JobPosting
from app.summarizers.prompts import SYSTEM_PROMPT, user_prompt
from app.summarizers.types import SummaryContext


def test_system_prompt_treats_fenced_blocks_as_data() -> None:
    assert "<<<JOB_POSTING>>>" in SYSTEM_PROMPT
    assert "untrusted data" in SYSTEM_PROMPT


def test_user_prompt_fences_scraped_posting_fields() -> None:
    job = JobPosting(
        external_id="1",
        title="Senior Engineer",
        company="ACME",
        location="Remote",
    )
    prompt = user_prompt(SummaryContext(search_name="Backend", filters={"keywords": "python"}), job)
    assert "<<<JOB_POSTING>>>" in prompt
    assert "<<<END_JOB_POSTING>>>" in prompt
    assert "- Title: Senior Engineer" in prompt
    assert "- Company: ACME" in prompt
    assert "- Location: Remote" in prompt
    assert prompt.index("<<<JOB_POSTING>>>") < prompt.index("- Title: Senior Engineer")
    assert prompt.index("- Title: Senior Engineer") < prompt.index("<<<END_JOB_POSTING>>>")
    assert "Saved search: Backend" in prompt
    assert "keywords=python" in prompt
    assert prompt.index("<<<END_JOB_POSTING>>>") < prompt.index("Saved search: Backend")


def test_user_prompt_skips_blank_posting_fields() -> None:
    job = JobPosting(external_id="9", title="")
    prompt = user_prompt(SummaryContext(filters={"unrelated_key": "x"}), job)
    assert "Search filters: none" in prompt
    assert "Saved search:" not in prompt
    assert "- Title:" not in prompt
