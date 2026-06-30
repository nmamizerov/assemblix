"""add is_debug to chat_sessions

Revision ID: a1b2c3d4e5f6
Revises: f5a6b7c8d9e0
Create Date: 2026-01-07 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_debug column to chat_sessions table
    with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_debug", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.create_index(
            batch_op.f("ix_chat_sessions_is_debug"), ["is_debug"], unique=False
        )


def downgrade() -> None:
    # Remove is_debug column from chat_sessions table
    with op.batch_alter_table("chat_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chat_sessions_is_debug"))
        batch_op.drop_column("is_debug")
