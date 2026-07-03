"""Tests for per-user summary settings overlay."""

from app.core.crypto import encrypt
from app.models.user import User
from app.scrapers.types import JobPosting
from app.services.summaries import SummaryService
from app.summarizers import SummaryContext
from app.summarizers.base import Summarizer
from app.summarizers.runtime_settings import resolve_summary_settings


class _Settings:
    def __init__(
        self,
        *,
        enabled: bool = True,
        provider: str = "heuristic",
        max_chars: int = 280,
        openai_api_key: str = "",
    ):
        self.summaries_enabled = enabled
        self.summary_provider = provider
        self.summary_max_chars = max_chars
        self.openai_api_key = openai_api_key


class _FakeSummarizer(Summarizer):
    def __init__(self, blurbs: list[str]) -> None:
        self.blurbs = blurbs
        self.calls: list[SummaryContext] = []
        self.settings = None

    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        self.calls.append(ctx)
        return self.blurbs


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(external_id=external_id, title="Engineer", company="ACME")


def test_annotate_sets_summary_in_place() -> None:
    fake = _FakeSummarizer(["because reasons"])
    service = SummaryService(
        summarizer_factory=lambda key, **kwargs: fake,
        settings=_Settings(),
    )
    jobs = [_job()]

    service.annotate(jobs, search_name="My search", filters={"keywords": "engineer"})

    assert jobs[0].summary == "because reasons"
    assert fake.calls[0].search_name == "My search"
    assert fake.calls[0].filters == {"keywords": "engineer"}


def test_annotate_noop_when_disabled() -> None:
    fake = _FakeSummarizer(["should not appear"])
    service = SummaryService(
        summarizer_factory=lambda key, **kwargs: fake,
        settings=_Settings(enabled=False),
    )
    jobs = [_job()]

    service.annotate(jobs)

    assert jobs[0].summary == ""
    assert fake.calls == []


def test_annotate_truncates_to_max_chars() -> None:
    fake = _FakeSummarizer(["x" * 50])
    service = SummaryService(
        summarizer_factory=lambda key, **kwargs: fake,
        settings=_Settings(max_chars=10),
    )
    jobs = [_job()]

    service.annotate(jobs)

    assert len(jobs[0].summary) == 10
    assert jobs[0].summary.endswith("\u2026")


def test_annotate_swallows_provider_errors() -> None:
    class _BoomSummarizer(Summarizer):
        def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
            raise RuntimeError("provider down")

    service = SummaryService(
        summarizer_factory=lambda key, **kwargs: _BoomSummarizer(),
        settings=_Settings(),
    )
    jobs = [_job()]

    service.annotate(jobs)

    assert jobs[0].summary == ""


def test_annotate_uses_user_provider_override() -> None:
    captured: dict[str, str] = {}

    class _RecordingSummarizer(Summarizer):
        def __init__(self, *, settings: _Settings | None = None) -> None:
            self._settings = settings

        def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
            captured["provider"] = str(self._settings.summary_provider)  # type: ignore[union-attr]
            return ["ok"]

    service = SummaryService(
        summarizer_factory=lambda key, **kwargs: _RecordingSummarizer(**kwargs),
        settings=_Settings(provider="heuristic"),
    )
    user = User(
        email="pro@example.com",
        password_hash="x",
        summary_provider="openai",
    )

    service.annotate([_job()], user=user)

    assert captured["provider"] == "openai"


def test_annotate_skips_blank_blurbs() -> None:
    """A blank/whitespace blurb leaves the posting summary untouched."""
    fake = _FakeSummarizer(["   "])
    service = SummaryService(
        summarizer_factory=lambda key, **kwargs: fake,
        settings=_Settings(),
    )
    jobs = [_job()]

    service.annotate(jobs)

    assert jobs[0].summary == ""


def test_resolve_summary_settings_uses_user_api_key() -> None:
    user = User(
        email="pro@example.com",
        password_hash="x",
        summary_provider="openai",
        summary_api_key_ciphertext=encrypt("user-secret"),
    )
    base = _Settings(provider="openai", openai_api_key="server-secret")

    resolved = resolve_summary_settings(base, user)

    assert resolved.summary_provider == "openai"
    assert resolved.openai_api_key == "user-secret"


def test_resolve_summary_settings_falls_back_to_server_key() -> None:
    user = User(email="pro@example.com", password_hash="x", summary_provider="openai")
    base = _Settings(provider="heuristic", openai_api_key="server-secret")

    resolved = resolve_summary_settings(base, user)

    assert resolved.summary_provider == "openai"
    assert resolved.openai_api_key == "server-secret"
