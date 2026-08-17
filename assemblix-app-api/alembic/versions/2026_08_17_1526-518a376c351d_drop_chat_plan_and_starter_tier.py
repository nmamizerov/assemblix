"""drop chat plan and starter tier

Revision ID: 518a376c351d
Revises: 78702bfa003e
Create Date: 2026-08-17 15:26:41.537522

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '518a376c351d'
down_revision = '78702bfa003e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Leftover 'starter' subscribers move up to 'pro' (not down) before the
    # STARTER tier is dropped from PlanTier; 'plan' is a plain VARCHAR, so a
    # stale 'starter' string would fail PlanTier(...) on load otherwise.
    op.execute("UPDATE organizations SET plan = 'pro' WHERE plan = 'starter'")

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_organizations_chat_plan'))
        batch_op.drop_column('chat_plan')


def downgrade() -> None:
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'chat_plan',
                sa.VARCHAR(length=50),
                server_default=sa.text("'free'::character varying"),
                autoincrement=False,
                nullable=False,
                comment='Plan tier for chat widgets',
            )
        )
        batch_op.create_index(
            batch_op.f('ix_organizations_chat_plan'), ['chat_plan'], unique=False
        )
