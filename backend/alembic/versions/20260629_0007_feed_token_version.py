"""add feed_token_version to user

Revision ID: 0007_feed_token_version
Revises: 0006_job_lifecycle
Create Date: 2026-06-29

Tracks RSS feed token rotation so previously issued feed URLs can be revoked.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_feed_token_version"
down_revision: str | None = "0006_job_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("feed_token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("user", "feed_token_version", server_default=None)


def downgrade() -> None:
    op.drop_column("user", "feed_token_version")
