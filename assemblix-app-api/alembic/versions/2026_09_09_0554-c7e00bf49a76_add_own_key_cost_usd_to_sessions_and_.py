"""add own key cost usd to sessions and voice agents

Revision ID: c7e00bf49a76
Revises: 8992986067da
Create Date: 2026-09-09 05:54:26.824043

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c7e00bf49a76'
down_revision = '8992986067da'
branch_labels = None
depends_on = None

COMMENT = "Total USD spent on the user's own provider keys (not billed as credits)"
TABLES = ("chat_sessions", "client_sessions", "voice_sessions", "voice_agents")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "own_key_cost_usd",
                sa.Numeric(precision=20, scale=8),
                nullable=False,
                server_default="0",
                comment=COMMENT,
            ),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "own_key_cost_usd")
