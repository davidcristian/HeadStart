"""widen inbox message UID columns to BigInteger

Revision ID: 0033_widen_inbox_uid_to_bigint
Revises: 0032_application_artifact
Create Date: 2026-07-03

Encoded mailbox UIDs (Outlook/Fastmail time-ordered ids, Gmail hex ids) exceed
the 32-bit INTEGER range on Postgres, so INSERTs fail the moment a real message
is polled. Widen the persisted UID columns to BIGINT. On Postgres these tables
are empty today (every provider's uid overflowed INTEGER, so no row ever
committed), so no data backfill is required -- this is a pure schema change.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033_widen_inbox_uid_to_bigint"
down_revision: str | None = "0032_application_artifact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, nullable) for each persisted mailbox UID column.
_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("inbox_classification", "message_uid", False),
    ("inbox_reply_draft", "message_uid", False),
    ("inbox_poll_state", "last_polled_uid", True),
)


def upgrade() -> None:
    # batch_alter_table emits a plain ALTER TYPE on Postgres and recreates the
    # table on SQLite (which cannot alter a column type in place).
    for table, column, nullable in _COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=nullable,
            )


def downgrade() -> None:
    for table, column, nullable in _COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                existing_type=sa.BigInteger(),
                type_=sa.Integer(),
                existing_nullable=nullable,
            )
