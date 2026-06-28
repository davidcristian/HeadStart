"""Shared helpers for batched digest notification messages."""

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


def digest_text_lines(jobs: list[JobPosting]) -> list[str]:
    """Human-readable lines, one block per job."""
    lines: list[str] = []
    for job in jobs:
        block = job_headline(job)
        if job.location:
            block = f"{block} ({job.location})"
        if job.url:
            block = f"{block}\n  {job.url}"
        lines.append(block)
    return lines


def digest_plain_body(jobs: list[JobPosting]) -> str:
    """Plain-text body listing every job in the digest."""
    return "\n\n".join(digest_text_lines(jobs))
