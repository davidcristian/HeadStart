"""Tests that pipeline runs update Prometheus counters."""

from sqlalchemy.orm import Session

from app.core.metrics import PIPELINE_RUNS, SCRAPE_RUNS
from app.models.base import utcnow
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.source import Source
from app.models.user import User
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting, ScrapeContext
from app.services.pipeline import PipelineService


class FakeScraper:
    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        return [
            JobPosting(
                external_id="1",
                title="Engineer",
                company="ACME",
                url="https://jobs.example/1",
            )
        ]


class RecordingNotifier:
    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        return [DeliveryResult(external_id=j.external_id, status="sent") for j in jobs]


def _make_search(session: Session) -> Search:
    user = User(email=f"metrics{utcnow().timestamp()}@example.test", password_hash="x")
    source = Source(
        user_id=0,
        name="src",
        adapter_key="greenhouse",
        base_url="",
        default_config={},
    )
    target = NotificationTarget(user_id=0, name="tgt", type="ntfy", config={"topic": "x"})
    session.add(user)
    session.flush()
    source.user_id = user.id
    target.user_id = user.id
    session.add_all([source, target])
    session.flush()
    search = Search(
        user_id=user.id,
        name="search",
        source_id=source.id,
        target_id=target.id,
        query_url="",
        filters={},
        config={},
        interval_seconds=300,
        enabled=True,
        next_run_at=utcnow(),
    )
    session.add(search)
    session.flush()
    return search


def _counter_value(counter: object, **labels: str) -> float:
    return float(counter.labels(**labels)._value.get())  # type: ignore[attr-defined]


def test_pipeline_records_scrape_and_run_metrics(db_session: Session) -> None:
    search = _make_search(db_session)
    before_pipeline = _counter_value(PIPELINE_RUNS, status="success")
    before_scrape = _counter_value(SCRAPE_RUNS, adapter="greenhouse", status="success")

    PipelineService(
        db_session,
        scraper_factory=lambda *_a, **_k: FakeScraper(),
        notifier_factory=lambda _t: RecordingNotifier(),
    ).run(search.id)

    assert _counter_value(PIPELINE_RUNS, status="success") == before_pipeline + 1
    assert _counter_value(SCRAPE_RUNS, adapter="greenhouse", status="success") == before_scrape + 1
