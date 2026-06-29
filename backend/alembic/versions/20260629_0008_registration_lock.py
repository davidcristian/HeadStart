"""add registration_lock singleton

Revision ID: 0008_registration_lock
Revises: 0007_feed_token_version
Create Date: 2026-06-29

Serializes account registration so only one bootstrap admin can be created.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_registration_lock"
down_revision: str | None = "0007_feed_token_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registration_lock",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bootstrap_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_registration_lock_bootstrap_user_id_user",
        "registration_lock",
        "user",
        ["bootstrap_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(sa.text("INSERT INTO registration_lock (id) VALUES (1)"))


def downgrade() -> None:
    op.drop_constraint(
        "fk_registration_lock_bootstrap_user_id_user",
        "registration_lock",
        type_="foreignkey",
    )
    op.drop_table("registration_lock")
