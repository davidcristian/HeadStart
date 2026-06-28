from unittest.mock import patch

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.email import EmailNotifier
from app.scrapers.types import JobPosting


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url="https://careers.example/jobs/1",
    )


@patch("app.notifiers.adapters.email.send_email")
def test_email_sends_expected_content(mock_send) -> None:
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"})

    results = notifier.send(ctx, [_job()])

    assert len(results) == 1
    assert results[0].status == "sent"
    mock_send.assert_called_once_with(
        to="me@example.com",
        subject="Software Engineer @ Google",
        body=(
            "Software Engineer\n"
            "Company: Google\n"
            "Location: Amsterdam\n"
            "Apply: https://careers.example/jobs/1"
        ),
    )


@patch("app.notifiers.adapters.email.send_email")
def test_email_records_smtp_failure_without_raising(mock_send) -> None:
    import smtplib

    mock_send.side_effect = smtplib.SMTPException("relay denied")
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"})

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error == "relay denied"


@patch("app.notifiers.adapters.email.send_email")
def test_email_records_missing_smtp_config(mock_send) -> None:
    from app.core.email import SmtpNotConfiguredError

    mock_send.side_effect = SmtpNotConfiguredError("SMTP is not configured")
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"})

    results = notifier.send(ctx, [_job()])

    assert results[0].status == "failed"
    assert "SMTP" in (results[0].error or "")


def test_email_requires_recipient() -> None:
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={})

    try:
        notifier.send(ctx, [_job()])
        raised = False
    except ValueError as exc:
        raised = True
        assert "config.to" in str(exc)

    assert raised


def test_registry_resolves_email() -> None:
    assert isinstance(get_notifier("email"), EmailNotifier)
