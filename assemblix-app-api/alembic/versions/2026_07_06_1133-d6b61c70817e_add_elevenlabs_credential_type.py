"""add elevenlabs credential type

Revision ID: d6b61c70817e
Revises: 46ef62e3e56e
Create Date: 2026-07-06 11:33:15.904286

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'd6b61c70817e'
down_revision = '46ef62e3e56e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE ... ADD VALUE to run outside a transaction;
    # Alembic's op.execute() handles this correctly. Autogenerate does not detect
    # enum value additions, so this migration is written by hand.
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'ELEVENLABS_TOKEN'")


def downgrade() -> None:
    # Postgres cannot DROP an enum value; no-op (matches existing enum migrations).
    pass
