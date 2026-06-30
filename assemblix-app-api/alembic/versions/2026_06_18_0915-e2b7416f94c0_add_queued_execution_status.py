"""add QUEUED execution status

Revision ID: e2b7416f94c0
Revises: 2b83435823c3
Create Date: 2026-06-18 09:15:17.412937

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2b7416f94c0'
down_revision = '2b83435823c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add QUEUED value to the native Postgres executionstatus enum.
    # IF NOT EXISTS makes this idempotent (safe to re-run).
    op.execute("ALTER TYPE executionstatus ADD VALUE IF NOT EXISTS 'QUEUED'")


def downgrade() -> None:
    # Postgres does not support DROP VALUE on an enum type without recreating it.
    # Leaving QUEUED in place is safe: old code ignores unknown enum labels.
    pass

