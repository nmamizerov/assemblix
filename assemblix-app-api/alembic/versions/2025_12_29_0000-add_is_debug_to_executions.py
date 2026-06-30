"""add is_debug to executions

Revision ID: d8e9f1a2b3c4
Revises: c497322e746b
Create Date: 2025-12-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d8e9f1a2b3c4"
down_revision = "c497322e746b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_debug column to executions table
    with op.batch_alter_table("executions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_debug", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.create_index(
            batch_op.f("ix_executions_is_debug"), ["is_debug"], unique=False
        )


def downgrade() -> None:
    # Remove is_debug column from executions table
    with op.batch_alter_table("executions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_executions_is_debug"))
        batch_op.drop_column("is_debug")
