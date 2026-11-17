"""add yandex ai studio token credential type

Revision ID: e9b3c5d7f1a2
Revises: cec2c3bcb629
Create Date: 2026-11-17 12:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e9b3c5d7f1a2"
down_revision = "cec2c3bcb629"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'YANDEX_AI_STUDIO_TOKEN'")


def downgrade() -> None:
    # Postgres cannot DROP an enum value; no-op (matches existing enum migrations).
    pass
