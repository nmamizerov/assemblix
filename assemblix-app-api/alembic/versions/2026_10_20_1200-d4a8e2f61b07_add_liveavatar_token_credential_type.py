"""add liveavatar_token credential type

Revision ID: d4a8e2f61b07
Revises: b1f7a9c3d2e4
Create Date: 2026-10-20 12:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "d4a8e2f61b07"
down_revision = "b1f7a9c3d2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Autogenerate does not detect enum value additions; written by hand.
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'LIVEAVATAR_TOKEN'")


def downgrade() -> None:
    # Postgres cannot DROP an enum value; no-op (matches existing enum migrations).
    pass
