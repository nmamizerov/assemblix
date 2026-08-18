"""split credit balance into granted and purchased

Revision ID: c17fcb95cdcb
Revises: ae3610dcc330
Create Date: 2026-08-18 03:04:31.106592

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c17fcb95cdcb'
down_revision = 'ae3610dcc330'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credits_granted_balance', sa.Numeric(precision=20, scale=8), server_default='0', nullable=False, comment='Granted credits, re-issued by the monthly plan grant'))
        batch_op.add_column(sa.Column('credits_purchased_balance', sa.Numeric(precision=20, scale=8), server_default='0', nullable=False, comment='Purchased credits, never expire'))

    op.execute("UPDATE organizations SET credits_granted_balance = credits_balance")

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('credits_balance')


def downgrade() -> None:
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credits_balance', sa.NUMERIC(precision=20, scale=8), autoincrement=False, nullable=False, server_default='0', comment='Current credit balance (up to 8 decimal places)'))

    op.execute(
        "UPDATE organizations "
        "SET credits_balance = credits_granted_balance + credits_purchased_balance"
    )

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('credits_purchased_balance')
        batch_op.drop_column('credits_granted_balance')
        batch_op.alter_column('credits_balance', server_default=None)
