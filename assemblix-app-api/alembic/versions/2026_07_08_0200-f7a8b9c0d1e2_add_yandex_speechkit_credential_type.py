"""add yandex speechkit credential type

Revision ID: f7a8b9c0d1e2
Revises: e1a2b3c4d5f6
Create Date: 2026-07-08 02:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'e1a2b3c4d5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE ... ADD VALUE to run outside a transaction;
    # Alembic's op.execute() handles this correctly. Autogenerate does not detect
    # enum value additions, so this migration is written by hand.
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'YANDEX_SPEECHKIT_TOKEN'")


def downgrade() -> None:
    # Postgres cannot DROP an enum value; no-op (matches existing enum migrations).
    pass
