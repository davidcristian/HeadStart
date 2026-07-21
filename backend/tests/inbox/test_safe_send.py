"""Unit tests for inbox safe-send topic blocklist."""

from app.inbox.safe_send import check_topic_blocklist, find_sensitive_topics


def test_find_sensitive_topics_matches_legal_phrases() -> None:
    matched = find_sensitive_topics(
        "Please contact our attorney regarding your application.",
        "Thanks for applying.",
    )
    assert "attorney" in matched


def test_check_topic_blocklist_ignores_normal_follow_up() -> None:
    assert (
        check_topic_blocklist(
            inbound_subject="Quick question",
            inbound_body="What is your availability next week?",
            draft_subject="Re: Quick question",
            draft_body="I am available Tuesday afternoon.",
        )
        is None
    )


def test_check_topic_blocklist_blocks_discrimination_thread() -> None:
    result = check_topic_blocklist(
        inbound_subject="HR follow-up",
        inbound_body="We are reviewing a discrimination complaint related to your interview.",
        draft_subject="Re: HR follow-up",
        draft_body="Thank you for the update.",
    )
    assert result is not None
    assert "discrimination" in result.matched_topics
    assert "Auto-reply blocked" in result.reason


def test_check_topic_blocklist_blocks_plain_workers_compensation() -> None:
    """Single-space spelling must match, not only the apostrophe form."""
    for body in (
        "Please discuss workers compensation with HR.",
        "Please discuss workers' compensation with HR.",
        "Please discuss workers’ compensation with HR.",
    ):
        result = check_topic_blocklist(
            inbound_subject="Benefits question",
            inbound_body=body,
            draft_subject="Re: Benefits question",
            draft_body="Happy to help.",
        )
        assert result is not None, body
        assert "workers_comp" in result.matched_topics
