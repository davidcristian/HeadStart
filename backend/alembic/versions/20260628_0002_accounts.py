"""multi-user accounts + encrypted site credentials

Revision ID: 0002_accounts
Revises: 0001_initial
Create Date: 2026-06-28

Adds the `user` and `site_credential` tables and a `user_id` owner column on
`source`, `search`, and `notification_target`. Existing rows (if any) are
backfilled to a bootstrap admin so the column can become NOT NULL.

The bootstrap admin is created only when pre-existing rows need an owner. Its
credentials come from BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD (with
safe defaults that should be changed immediately after upgrade).
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_accounts"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWNED_TABLES = ("source", "search", "notification_target")


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "site_credential",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_site_credential_user_id", "site_credential", ["user_id"])
    op.create_index("ix_site_credential_source_id", "site_credential", ["source_id"])

    # 1) Add nullable owner columns.
    for table in _OWNED_TABLES:
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))

    # 2) Backfill existing rows to a bootstrap admin (only if any exist).
    admin_id = _backfill_owner()

    # 3) Lock the columns down: NOT NULL + FK + index.
    for table in _OWNED_TABLES:
        if admin_id is None:
            # No data to backfill; still safe to require ownership going forward.
            op.alter_column(table, "user_id", existing_type=sa.Integer(), nullable=False)
        else:
            op.alter_column(table, "user_id", existing_type=sa.Integer(), nullable=False)
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_foreign_key(
            f"fk_{table}_user_id",
            table,
            "user",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def _backfill_owner() -> int | None:
    """Create a bootstrap admin and assign all orphan rows to it. Returns its id."""
    bind = op.get_bind()
    has_rows = any(
        bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None
        for table in _OWNED_TABLES
    )
    if not has_rows:
        return None

    # Imported lazily so the module loads even if app deps shift over time.
    from app.core.security import hash_password

    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "change-me-admin-password")

    from app.models.base import utcnow

    admin_id = bind.execute(
        sa.text(
            'INSERT INTO "user" (email, password_hash, is_admin, is_active, created_at) '
            "VALUES (:email, :pw, true, true, :now) RETURNING id"
        ),
        {"email": email, "pw": hash_password(password), "now": utcnow()},
    ).scalar_one()

    for table in _OWNED_TABLES:
        bind.execute(
            sa.text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
            {"uid": admin_id},
        )
    return int(admin_id)


def downgrade() -> None:
    for table in _OWNED_TABLES:
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
    op.drop_table("site_credential")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
