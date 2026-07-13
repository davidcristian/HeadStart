"""add server_default for inbox_reply_send_log text cols

Revision ID: 0045_reply_send_defaults
Revises: 0044_token_used_at
Create Date: 2026-07-13

Migration 0031 created reason/subject/body_excerpt as NOT NULL without
server_default, while the ORM only supplies default='' (DAT-08). Sibling
inbox_classification (0024) already uses server_default=''. Patch existing
DBs that applied 0031 before the create_table was corrected.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0045_reply_send_defaults"
down_revision: str | None = "0044_token_used_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "inbox_reply_send_log"
_COLUMNS = ("reason", "subject", "body_excerpt")


def upgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(_TABLE, column, server_default="")


def downgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(_TABLE, column, server_default=None)
