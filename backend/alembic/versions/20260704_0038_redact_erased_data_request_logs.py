"""redact PII on orphaned / delete GDPR audit rows

Revision ID: 0038_redact_data_req
Revises: 0037_reg_lock_claimed
Create Date: 2026-07-04

Historical delete (and orphaned export) rows kept plaintext email/IP/UA after
account erasure. Replace recoverable identifiers with a static marker; new
deletes write an HMAC pseudonym instead (see auth_account._record_data_request).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0038_redact_data_req"
down_revision: str | None = "0037_reg_lock_claimed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE data_request_log
            SET user_email = 'erased',
                ip_address = NULL,
                user_agent = NULL
            WHERE request_type = 'delete'
               OR user_id IS NULL
            """
        )
    )


def downgrade() -> None:
    # Irreversible redaction — prior plaintext cannot be restored.
    pass
