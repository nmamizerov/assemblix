"""add typesafe_token credential type

Revision ID: cec2c3bcb629
Revises: d4a8e2f61b07
Create Date: 2026-10-28 07:01:20.026656

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "cec2c3bcb629"
down_revision = "d4a8e2f61b07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE ... ADD VALUE to run outside a transaction;
    # Alembic's op.execute() handles this correctly. Autogenerate does not detect
    # enum value additions, so this migration is written by hand.
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'TYPESAFE_TOKEN'")


def downgrade() -> None:
    # Postgres cannot DROP an enum value; no-op (matches existing enum migrations).
    pass
