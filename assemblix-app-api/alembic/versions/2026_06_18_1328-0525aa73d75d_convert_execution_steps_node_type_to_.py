"""convert execution_steps.node_type to varchar

Revision ID: 0525aa73d75d
Revises: e2b7416f94c0
Create Date: 2026-06-18 13:28:07.449715

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0525aa73d75d'
down_revision = 'e2b7416f94c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "execution_steps", "node_type",
        type_=sa.String(length=100), existing_nullable=False,
        postgresql_using="node_type::text",
    )
    # Normalise legacy uppercase enum names (e.g. 'AGENT') to the lowercase
    # wire values the rest of the system expects (e.g. 'agent').
    op.execute("UPDATE execution_steps SET node_type = lower(node_type)")
    # Drop the now-orphaned enum type (no other column references it).
    op.execute("DROP TYPE IF EXISTS nodetype")


def downgrade() -> None:
    nodetype = sa.Enum(
        "START", "AGENT", "CONDITION", "SET_VARIABLE", "END",
        "STICKER", "HTTP_REQUEST", name="nodetype",
    )
    nodetype.create(op.get_bind(), checkfirst=True)
    # Restore uppercase values so the cast back to the PG enum succeeds.
    op.execute("UPDATE execution_steps SET node_type = upper(node_type)")
    op.alter_column(
        "execution_steps", "node_type",
        type_=nodetype, existing_nullable=False,
        postgresql_using="node_type::nodetype",
    )
