"""make payments target_plan nullable

Revision ID: ae3610dcc330
Revises: 518a376c351d
Create Date: 2026-08-17 15:40:18.351116

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ae3610dcc330'
down_revision = '518a376c351d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable so a legacy 'starter' string (unparseable now that the tier is
    # gone) and future non-plan payments (e.g. credit packs) don't need a
    # placeholder value.
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.alter_column(
            'target_plan',
            existing_type=sa.VARCHAR(length=50),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.alter_column(
            'target_plan',
            existing_type=sa.VARCHAR(length=50),
            nullable=False,
        )
