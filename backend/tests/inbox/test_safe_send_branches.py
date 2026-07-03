"""Branch coverage for the safe-send topic blocklist (empty-input path)."""

from app.inbox.safe_send import check_topic_blocklist, find_sensitive_topics


def test_find_sensitive_topics_returns_empty_for_blank_inputs() -> None:
    assert find_sensitive_topics("", "   ", "") == []


def test_check_topic_blocklist_returns_none_for_blank_inputs() -> None:
    assert check_topic_blocklist() is None
