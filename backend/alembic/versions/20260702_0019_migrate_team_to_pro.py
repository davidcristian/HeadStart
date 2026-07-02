"""migrate team plan to pro

Revision ID: 0019_migrate_team_to_pro
Revises: 0018_email_verification
Create Date: 2026-07-02

Deprecates the admin-only team tier in favor of the four-tier ladder (ADR-0010).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_migrate_team_to_pro"
down_revision: str | None = "0018_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE \"user\" SET plan = 'pro' WHERE plan = 'team'")


def downgrade() -> None:
    pass
