"""Shared fakes and helpers for pipeline integration tests."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.source import Source
from app.models.user import User
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting, ScrapeContext
from app.services.pipeline import PipelineService


class FakeScraper:
    def __init__(self, postings: list[JobPosting]) -> None:
        self.postings = postings
        self.last_ctx: ScrapeContext | None = None

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        self.last_ctx = ctx
        return self.postings


class RecordingNotifier:
    def __init__(self) -> None:
        self.batches: list[list[JobPosting]] = []

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        self.batches.append(list(jobs))
        return [DeliveryResult(external_id=j.external_id, status="sent") for j in jobs]


class FailingScraper:
    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        raise ValueError("scrape blew up")


def make_user(session: Session, email: str = "pipe@example.test") -> User:
    user = User(email=email, password_hash="x", is_admin=True, is_active=True)
    session.add(user)
    session.flush()
    return user


def make_search(
    session: Session,
    *,
    interval: int = 300,
    next_run_at=None,
    user: User | None = None,
) -> Search:
    owner = user or make_user(session, email=f"pipe{utcnow().timestamp()}@example.test")
    source = Source(
        user_id=owner.id, name="src", adapter_key="greenhouse", base_url="", default_config={}
    )
    target = NotificationTarget(user_id=owner.id, name="tgt", type="ntfy", config={"topic": "x"})
    session.add_all([source, target])
    session.flush()
    search = Search(
        user_id=owner.id,
        name="search",
        source_id=source.id,
        target_id=target.id,
        query_url="",
        filters={},
        config={},
        interval_seconds=interval,
        enabled=True,
        next_run_at=next_run_at or utcnow(),
    )
    session.add(search)
    session.flush()
    return search


def aware(dt: datetime) -> datetime:
    """Coerce to tz-aware UTC. SQLite returns naive datetimes; Postgres does not."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def posting(external_id: str, *, url: str | None = None) -> JobPosting:
    job_url = url if url is not None else f"https://acme.test/{external_id}"
    return JobPosting(
        external_id=external_id,
        title=f"Job {external_id}",
        company="ACME",
        location="Amsterdam",
        url=job_url,
    )


def pipeline(
    session: Session, scraper: FakeScraper, notifier: RecordingNotifier
) -> PipelineService:
    return PipelineService(
        session,
        scraper_factory=lambda key, http=None, rate_limiter=None: scraper,  # type: ignore[arg-type,return-value]
        notifier_factory=lambda key: notifier,  # type: ignore[arg-type,return-value]
    )
