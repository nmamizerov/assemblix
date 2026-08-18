"""add payment kind and nullable target plan

Revision ID: 4de7fb88cd1f
Revises: c17fcb95cdcb
Create Date: 2026-08-18 07:47:39.658452

Trimmed from the raw autogenerate output: the raw diff also carried ~700 lines of
unrelated column-comment drift (pre-existing Russian-vs-English comment mismatches
across nearly every table) and two index uniqueness flips picked up from the live
DB, none of which are part of this task. Only the ``payments.kind`` column --
this migration's actual purpose -- is kept. ``payments.target_plan`` was already
made nullable by a prior migration (``ae3610dcc330``), so no column change was
needed for it here.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4de7fb88cd1f'
down_revision = 'c17fcb95cdcb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'kind',
                sa.String(length=32),
                server_default='subscription',
                nullable=False,
                comment='What the payment is for: subscription or credit_pack',
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_column('kind')
