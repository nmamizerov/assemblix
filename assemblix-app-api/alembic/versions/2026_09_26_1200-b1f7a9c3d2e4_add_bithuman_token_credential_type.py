"""add bithuman_token credential type

Revision ID: b1f7a9c3d2e4
Revises: c7e00bf49a76
Create Date: 2026-09-26 12:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b1f7a9c3d2e4"
down_revision = "c7e00bf49a76"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Autogenerate does not detect enum value additions; written by hand.
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'BITHUMAN_TOKEN'")


def downgrade() -> None:
    # Postgres cannot DROP an enum value; no-op (matches existing enum migrations).
    pass
