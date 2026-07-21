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
def test_email_includes_summary_line(mock_send) -> None:
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"})
    job = _job()
    job.summary = "Matches your search: mentions engineer."

    notifier.send(ctx, [job])

    body = mock_send.call_args.kwargs["body"]
    assert "Why this matches: Matches your search: mentions engineer." in body


@patch("app.notifiers.adapters.email.send_email")
def test_email_localizes_field_labels(mock_send) -> None:
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"}, locale="de")
    job = _job()
    job.summary = "Passt gut."

    notifier.send(ctx, [job])

    body = mock_send.call_args.kwargs["body"]
    assert "Warum das passt: Passt gut." in body
    assert "Unternehmen: Google" in body
    assert "Ort: Amsterdam" in body
    assert "Bewerben: https://careers.example/jobs/1" in body


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


@patch("app.notifiers.adapters.email.send_email")
def test_email_body_omits_absent_fields(mock_send) -> None:
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"})
    job = JobPosting(external_id="1", title="Engineer")
    notifier.send(ctx, [job])

    kwargs = mock_send.call_args.kwargs
    assert kwargs["subject"] == "Engineer"
    assert kwargs["body"] == "Engineer"


@patch("app.notifiers.adapters.email.send_email")
def test_email_digest_sends_single_email(mock_send) -> None:
    notifier = EmailNotifier()
    ctx = NotifyContext(
        target_type="email",
        config={"to": "me@example.com"},
        digest=True,
        search_name="Backend",
    )
    results = notifier.send(ctx, [_job("1"), _job("2")])

    assert len(results) == 2
    assert all(r.status == "sent" for r in results)
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["subject"] == "2 new jobs for Backend"
    assert "Software Engineer @ Google" in kwargs["body"]


def test_email_digest_empty_jobs_returns_empty() -> None:
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"}, digest=True)
    assert notifier.send(ctx, []) == []


@patch("app.notifiers.adapters.email.send_email")
def test_email_digest_records_smtp_not_configured(mock_send) -> None:
    from app.core.email import SmtpNotConfiguredError

    mock_send.side_effect = SmtpNotConfiguredError("SMTP not configured")
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"}, digest=True)
    results = notifier.send(ctx, [_job("1"), _job("2")])
    assert [r.status for r in results] == ["failed", "failed"]
    assert "SMTP" in (results[0].error or "")


@patch("app.notifiers.adapters.email.send_email")
def test_email_digest_records_smtp_exception(mock_send) -> None:
    import smtplib

    mock_send.side_effect = smtplib.SMTPException("relay denied")
    notifier = EmailNotifier()
    ctx = NotifyContext(target_type="email", config={"to": "me@example.com"}, digest=True)
    results = notifier.send(ctx, [_job("1"), _job("2")])
    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error == "relay denied"


def test_registry_resolves_email() -> None:
    assert isinstance(get_notifier("email"), EmailNotifier)
