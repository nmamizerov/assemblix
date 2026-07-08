"""add anam_token credential type

Revision ID: e1a2b3c4d5f6
Revises: d6b61c70817e
Create Date: 2026-07-08 01:50:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5f6'
down_revision = 'd6b61c70817e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE ... ADD VALUE to run outside a transaction;
    # Alembic's op.execute() handles this correctly. Autogenerate does not detect
    # enum value additions, so this migration is written by hand.
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'ANAM_TOKEN'")


def downgrade() -> None:
    # Postgres cannot DROP an enum value; no-op (matches existing enum migrations).
    pass
