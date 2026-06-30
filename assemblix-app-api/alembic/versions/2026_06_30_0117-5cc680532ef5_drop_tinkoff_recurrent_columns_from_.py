"""drop tinkoff recurrent columns from payments

Revision ID: 5cc680532ef5
Revises: ebbf8443c420
Create Date: 2026-06-30 01:17:27.840765

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '5cc680532ef5'
down_revision = 'ebbf8443c420'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the Tinkoff-only recurrent-charge columns. Paddle renews
    # subscriptions via webhooks, so RebillId / parent payment chaining is no
    # longer used.
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('payments_parent_payment_id_fkey'), type_='foreignkey'
        )
        batch_op.drop_column('rebill_id')
        batch_op.drop_column('parent_payment_id')


def downgrade() -> None:
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'parent_payment_id',
                sa.UUID(),
                autoincrement=False,
                nullable=True,
                comment='ID родительского платежа (для рекуррентных списаний)',
            )
        )
        batch_op.add_column(
            sa.Column(
                'rebill_id',
                sa.BIGINT(),
                autoincrement=False,
                nullable=True,
                comment='ID для автоматического списания (RebillId от Tinkoff)',
            )
        )
        batch_op.create_foreign_key(
            batch_op.f('payments_parent_payment_id_fkey'),
            'payments',
            ['parent_payment_id'],
            ['id'],
            ondelete='SET NULL',
        )
