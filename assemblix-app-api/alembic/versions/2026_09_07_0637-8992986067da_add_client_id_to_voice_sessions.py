"""add client_id to voice_sessions

Revision ID: 8992986067da
Revises: 4de7fb88cd1f
Create Date: 2026-09-07 06:37:58.328624

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8992986067da'
down_revision = '4de7fb88cd1f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('voice_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client_id', sa.String(length=255), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_voice_sessions_client_id'), ['client_id'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('voice_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_voice_sessions_client_id'))
        batch_op.drop_column('client_id')
