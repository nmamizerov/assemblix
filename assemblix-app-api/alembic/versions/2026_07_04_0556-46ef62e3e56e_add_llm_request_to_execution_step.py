"""add llm_request to execution_step

Revision ID: 46ef62e3e56e
Revises: 5cc680532ef5
Create Date: 2026-07-04 05:56:50.025959

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '46ef62e3e56e'
down_revision = '5cc680532ef5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'execution_steps',
        sa.Column('llm_request', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('execution_steps', 'llm_request')
