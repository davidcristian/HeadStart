"""Tests for the mailbox connector registry."""

import pytest

from app.inbox.base import (
    MailboxConnector,
    available_mailboxes,
    get_mailbox,
    register_mailbox,
)


def test_get_mailbox_returns_registered_adapter() -> None:
    adapter = get_mailbox("imap_smtp")
    assert isinstance(adapter, MailboxConnector)


def test_get_mailbox_unknown_key_raises() -> None:
    with pytest.raises(KeyError, match="No mailbox connector registered"):
        get_mailbox("does-not-exist")


def test_available_mailboxes_includes_builtins() -> None:
    available = available_mailboxes()
    assert {"gmail", "outlook", "yahoo", "fastmail", "imap_smtp"} <= set(available)


def test_register_mailbox_rejects_duplicate_key() -> None:
    @register_mailbox("test-dup-connector")
    class _First(MailboxConnector):  # pragma: no cover - abstract stub
        def fetch_messages(self, ctx, *, since_uid=None, limit=50):  # type: ignore[override]
            raise NotImplementedError

        def send_message(self, ctx, message):  # type: ignore[override]
            raise NotImplementedError

        def test_connection(self, ctx):  # type: ignore[override]
            raise NotImplementedError

        def move_message(self, ctx, *, uid, destination, provider_message_id=None):  # type: ignore[override]
            raise NotImplementedError

    with pytest.raises(ValueError, match="already registered"):

        @register_mailbox("test-dup-connector")
        class _Second(MailboxConnector):  # pragma: no cover - abstract stub
            def fetch_messages(self, ctx, *, since_uid=None, limit=50):  # type: ignore[override]
                raise NotImplementedError

            def send_message(self, ctx, message):  # type: ignore[override]
                raise NotImplementedError

            def test_connection(self, ctx):  # type: ignore[override]
                raise NotImplementedError

            def move_message(self, ctx, *, uid, destination, provider_message_id=None):  # type: ignore[override]
                raise NotImplementedError


def test_register_mailbox_is_idempotent_for_same_class() -> None:
    @register_mailbox("test-idempotent-connector")
    class _Conn(MailboxConnector):  # pragma: no cover - abstract stub
        def fetch_messages(self, ctx, *, since_uid=None, limit=50):  # type: ignore[override]
            raise NotImplementedError

        def send_message(self, ctx, message):  # type: ignore[override]
            raise NotImplementedError

        def test_connection(self, ctx):  # type: ignore[override]
            raise NotImplementedError

        def move_message(self, ctx, *, uid, destination, provider_message_id=None):  # type: ignore[override]
            raise NotImplementedError

    # Re-registering the same class under the same key must not raise.
    assert register_mailbox("test-idempotent-connector")(_Conn) is _Conn
