"""Tests for high-priority application alert delivery."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.notifiers.types import DeliveryResult
from app.services.application_alerts import ApplicationAlertService
from tests.worker.pipeline_helpers import make_user
from tests.worker.test_pipeline import _make_search


def _seed_job_with_target(session: Session) -> tuple[int, SeenJob, NotificationTarget]:
    search = _make_search(session)
    target = session.get(NotificationTarget, search.target_id)
    assert target is not None
    job = SeenJob(
        search_id=search.id,
        external_id="job-1",
        hash="h1",
        title="Backend Engineer",
        company="ACME",
        location="Remote",
        url="https://careers.acme.com/jobs/1",
        status="applied",
        applied_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    session.add(job)
    session.flush()
    return search.user_id, job, target


def test_notify_interview_handoff_sends_high_priority_ntfy(db_session: Session) -> None:
    user_id, job, target = _seed_job_with_target(db_session)
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"interview-handoff-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        results = service.notify_interview_handoff(user_id, job, email_subject="Phone screen")

    assert len(results) == 1
    assert results[0].status == "sent"
    mock_notifier.send.assert_called_once()
    ctx, postings = mock_notifier.send.call_args.args
    assert ctx.config["priority"] == "high"
    assert postings[0].title == "Phone screen"
    assert "ACME" in postings[0].summary


def test_alert_delivery_is_audited_to_delivery_log(db_session: Session) -> None:
    """Regression: alert sends must write a DeliveryLog row like the other paths."""
    user_id, job, target = _seed_job_with_target(db_session)
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"interview-handoff-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        service.notify_interview_handoff(user_id, job)

    db_session.flush()  # the classify flow's session_scope flushes/commits in prod
    logs = db_session.query(DeliveryLog).filter_by(seen_job_id=job.id).all()
    assert len(logs) == 1
    assert logs[0].target_id == target.id
    assert logs[0].status == "sent"


def test_notify_ghost_recovery_uses_rejection_copy(db_session: Session) -> None:
    user_id, job, _target = _seed_job_with_target(db_session)
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"ghost-recovery-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        results = service.notify_ghost_recovery(user_id, job, label="rejection")

    assert results[0].status == "sent"
    postings = mock_notifier.send.call_args.args[1]
    assert "rejection" in postings[0].summary.lower()


def test_alert_records_failure_when_notifier_raises(db_session: Session) -> None:
    user_id, job, target = _seed_job_with_target(db_session)
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.side_effect = RuntimeError("ntfy down")

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        results = service.notify_interview_handoff(user_id, job)

    assert len(results) == 1
    assert results[0].status == "failed"
    assert "ntfy down" in (results[0].error or "")
    db_session.flush()
    logs = db_session.query(DeliveryLog).filter_by(seen_job_id=job.id).all()
    assert len(logs) == 1
    assert logs[0].status == "failed"
    # A notifier exposing close() gets closed in the finally block.
    mock_notifier.close.assert_called_once()


def test_alert_handles_notifier_without_close(db_session: Session) -> None:
    user_id, job, target = _seed_job_with_target(db_session)
    service = ApplicationAlertService(db_session)

    class NotifierNoClose:
        def send(self, ctx, jobs):
            return [DeliveryResult(external_id=jobs[0].external_id, status="sent")]

    with patch("app.services.application_alerts.get_notifier", return_value=NotifierNoClose()):
        results = service.notify_interview_handoff(user_id, job)

    assert results[0].status == "sent"


def test_alert_falls_back_to_all_targets_when_search_target_missing(db_session: Session) -> None:
    user_id, job, target = _seed_job_with_target(db_session)
    # Drop the search's target link so resolution falls back to list_all.
    job.search.target_id = None
    db_session.flush()
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"interview-handoff-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        results = service.notify_interview_handoff(user_id, job)

    assert results[0].status == "sent"


def test_alert_falls_back_when_search_target_id_unresolvable(db_session: Session) -> None:
    user_id, job, target = _seed_job_with_target(db_session)
    # target_id set but points at a row that does not resolve for this user.
    job.search.target_id = 987654
    db_session.flush()
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"interview-handoff-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        results = service.notify_interview_handoff(user_id, job)

    # Falls through to list_all, which still finds the seeded target.
    assert results[0].status == "sent"


def test_alert_non_ntfy_target_has_no_priority(db_session: Session) -> None:
    user_id, job, target = _seed_job_with_target(db_session)
    target.type = "email"
    target.config = {"to": "me@example.com"}
    db_session.flush()
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"interview-handoff-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        service.notify_interview_handoff(user_id, job)

    ctx = mock_notifier.send.call_args.args[0]
    assert "priority" not in ctx.config


def test_notify_ghost_recovery_uses_interview_copy(db_session: Session) -> None:
    user_id, job, _target = _seed_job_with_target(db_session)
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"ghost-recovery-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        service.notify_ghost_recovery(user_id, job, label="interview_request")

    posting = mock_notifier.send.call_args.args[1][0]
    assert "interview" in posting.summary.lower()
    assert "Interview to schedule" in posting.title


def test_notify_ghost_recovery_uses_generic_copy(db_session: Session) -> None:
    user_id, job, _target = _seed_job_with_target(db_session)
    service = ApplicationAlertService(db_session)
    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [
        DeliveryResult(external_id=f"ghost-recovery-{job.id}", status="sent")
    ]

    with patch("app.services.application_alerts.get_notifier", return_value=mock_notifier):
        service.notify_ghost_recovery(user_id, job, label="follow_up")

    posting = mock_notifier.send.call_args.args[1][0]
    assert "responded" in posting.summary.lower()
    assert "replied after you marked this ghosted" in posting.title


def test_notify_returns_empty_when_user_has_no_targets(db_session: Session) -> None:
    user = make_user(db_session, email="no-targets@example.test")
    source = Source(
        user_id=user.id,
        name="src",
        adapter_key="greenhouse",
        base_url="",
        default_config={},
    )
    db_session.add(source)
    db_session.flush()
    search = Search(
        user_id=user.id,
        name="search",
        source_id=source.id,
        target_id=None,
        query_url="",
        filters={},
        config={},
        interval_seconds=300,
        enabled=True,
    )
    db_session.add(search)
    db_session.flush()
    job = SeenJob(
        search_id=search.id,
        external_id="job-2",
        hash="h2",
        title="Engineer",
        company="Beta",
        location="Remote",
        url="https://example.com/jobs/2",
        status="applied",
    )
    db_session.add(job)
    db_session.flush()
    service = ApplicationAlertService(db_session)
    results = service.notify_interview_handoff(user.id, job)
    assert results == []
