"""add call_details to voice_sessions

Revision ID: c60809265e07
Revises: c7e00bf49a76
Create Date: 2026-10-03 15:17:55.755115

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c60809265e07'
down_revision = 'c7e00bf49a76'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "voice_sessions",
        sa.Column("call_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("voice_sessions", "call_details")

