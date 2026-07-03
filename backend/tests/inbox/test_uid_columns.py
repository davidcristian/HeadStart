"""The persisted mailbox UID columns must be BigInteger.

SQLite's arbitrary-precision ints hide the overflow in tests, so guard the
declared column type directly: a 32-bit INTEGER overflows on Postgres.
"""

from sqlalchemy import BigInteger

from app.models.inbox_classification import InboxClassification
from app.models.inbox_poll_state import InboxPollState
from app.models.inbox_reply_draft import InboxReplyDraft


def test_inbox_uid_columns_are_bigint() -> None:
    columns = (
        InboxClassification.__table__.c.message_uid,
        InboxReplyDraft.__table__.c.message_uid,
        InboxPollState.__table__.c.last_polled_uid,
    )
    for column in columns:
        # BigInteger subclasses Integer, so a plain Integer column fails this.
        assert isinstance(column.type, BigInteger), column
