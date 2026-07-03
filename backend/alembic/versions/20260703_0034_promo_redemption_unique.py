"""unique redemption per (promo_code, user)

Revision ID: 0034_promo_redemption_unique
Revises: 0033_widen_inbox_uid_to_bigint
Create Date: 2026-07-03

Promo redemption was a read-then-write with no DB guard, so a webhook retry or
concurrent delivery could insert two rows for the same (promo_code_id, user_id)
and double-count the global redemption counter. Enforce one redemption per user
per promo at the database level; the service catches the resulting IntegrityError
and treats the duplicate as a no-op. De-dupe any pre-existing duplicates first
(keep the earliest row) so the constraint can be created.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034_promo_redemption_unique"
down_revision: str | None = "0033_widen_inbox_uid_to_bigint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "uq_promo_redemption_user"


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM promo_redemption
        WHERE id NOT IN (
            SELECT MIN(id) FROM promo_redemption GROUP BY promo_code_id, user_id
        )
        """
    )
    with op.batch_alter_table("promo_redemption") as batch:
        batch.create_unique_constraint(_CONSTRAINT, ["promo_code_id", "user_id"])


def downgrade() -> None:
    with op.batch_alter_table("promo_redemption") as batch:
        batch.drop_constraint(_CONSTRAINT, type_="unique")
