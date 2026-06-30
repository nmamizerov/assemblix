"""add api_keys table

Revision ID: e1f2a3b4c5d6
Revises: d8e9f1a2b3c4
Create Date: 2025-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d8e9f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_api_keys_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
    )

    # Create indexes
    op.create_index(
        op.f("ix_api_keys_user_id"),
        "api_keys",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_api_keys_prefix"),
        "api_keys",
        ["prefix"],
        unique=False,
    )
    op.create_index(
        op.f("ix_api_keys_is_active"),
        "api_keys",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_api_keys_user_id_active",
        "api_keys",
        ["user_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_api_keys_user_id_active", table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_is_active"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys")

    # Drop table
    op.drop_table("api_keys")
