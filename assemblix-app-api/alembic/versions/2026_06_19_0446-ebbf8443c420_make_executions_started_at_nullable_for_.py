"""make executions.started_at nullable for QUEUED

Revision ID: ebbf8443c420
Revises: 0525aa73d75d
Create Date: 2026-06-19 04:46:12.141424

"""
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = 'ebbf8443c420'
down_revision = '0525aa73d75d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A QUEUED execution is pre-created by the queue tier (create_queued) before any
    # worker starts it, so started_at is unknown until mark_running backfills it. The
    # NOT NULL constraint made every queued run fail at INSERT.
    op.alter_column(
        'executions',
        'started_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
    )


def downgrade() -> None:
    # NOTE: this will fail if any QUEUED rows with NULL started_at exist; backfill
    # (e.g. SET started_at = created_at WHERE started_at IS NULL) before downgrading.
    op.alter_column(
        'executions',
        'started_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
    )

