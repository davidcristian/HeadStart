"""Shared helpers for batched digest notification messages."""

from dataclasses import dataclass

from app.scrapers.types import JobPosting


def job_headline(job: JobPosting) -> str:
    """One-line summary for a single job."""
    title = job.title or "New job"
    return f"{title} @ {job.company}" if job.company else title


def digest_title(count: int, search_name: str | None = None) -> str:
    """Short title for a batched digest notification."""
    noun = "job" if count == 1 else "jobs"
    base = f"{count} new {noun}"
    if search_name:
        return f"{base} — {search_name}"
    return base


@dataclass
class DigestBlock:
    """Structured per-job content so each channel can format it natively."""

    headline: str
    summary: str
    url: str


def digest_blocks(jobs: list[JobPosting]) -> list[DigestBlock]:
    """One structured block per job (headline, optional summary, optional url)."""
    blocks: list[DigestBlock] = []
    for job in jobs:
        headline = job_headline(job)
        if job.location:
            headline = f"{headline} ({job.location})"
        blocks.append(DigestBlock(headline=headline, summary=job.summary, url=job.url))
    return blocks


def digest_text_lines(jobs: list[JobPosting]) -> list[str]:
    """Human-readable lines, one block per job (used by plain-text channels)."""
    lines: list[str] = []
    for block in digest_blocks(jobs):
        text = block.headline
        if block.summary:
            text = f"{text}\n  {block.summary}"
        if block.url:
            text = f"{text}\n  {block.url}"
        lines.append(text)
    return lines


def digest_plain_body(jobs: list[JobPosting]) -> str:
    """Plain-text body listing every job in the digest."""
    return "\n\n".join(digest_text_lines(jobs))
