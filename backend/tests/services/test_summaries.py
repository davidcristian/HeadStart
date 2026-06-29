from app.scrapers.types import JobPosting
from app.services.summaries import SummaryService
from app.summarizers import SummaryContext
from app.summarizers.base import Summarizer


class _Settings:
    def __init__(self, *, enabled: bool = True, provider: str = "fake", max_chars: int = 280):
        self.summaries_enabled = enabled
        self.summary_provider = provider
        self.summary_max_chars = max_chars


class _FakeSummarizer(Summarizer):
    def __init__(self, blurbs: list[str]) -> None:
        self.blurbs = blurbs
        self.calls: list[SummaryContext] = []

    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        self.calls.append(ctx)
        return self.blurbs


class _BoomSummarizer(Summarizer):
    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        raise RuntimeError("provider down")


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(external_id=external_id, title="Engineer", company="ACME")


def test_annotate_sets_summary_in_place() -> None:
    fake = _FakeSummarizer(["because reasons"])
    service = SummaryService(summarizer_factory=lambda key: fake, settings=_Settings())
    jobs = [_job()]

    service.annotate(jobs, search_name="My search", filters={"keywords": "engineer"})

    assert jobs[0].summary == "because reasons"
    assert fake.calls[0].search_name == "My search"
    assert fake.calls[0].filters == {"keywords": "engineer"}


def test_annotate_noop_when_disabled() -> None:
    fake = _FakeSummarizer(["should not appear"])
    service = SummaryService(summarizer_factory=lambda key: fake, settings=_Settings(enabled=False))
    jobs = [_job()]

    service.annotate(jobs)

    assert jobs[0].summary == ""
    assert fake.calls == []


def test_annotate_truncates_to_max_chars() -> None:
    fake = _FakeSummarizer(["x" * 50])
    service = SummaryService(summarizer_factory=lambda key: fake, settings=_Settings(max_chars=10))
    jobs = [_job()]

    service.annotate(jobs)

    assert len(jobs[0].summary) == 10
    assert jobs[0].summary.endswith("\u2026")


def test_annotate_swallows_provider_errors() -> None:
    service = SummaryService(summarizer_factory=lambda key: _BoomSummarizer(), settings=_Settings())
    jobs = [_job()]

    service.annotate(jobs)

    assert jobs[0].summary == ""
