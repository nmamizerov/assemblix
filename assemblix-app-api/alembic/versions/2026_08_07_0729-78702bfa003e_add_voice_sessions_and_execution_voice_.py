"""add voice_sessions and execution voice_session_id

Revision ID: 78702bfa003e
Revises: ea30b38221b9
Create Date: 2026-08-07 07:29:58.689065

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "78702bfa003e"
down_revision = "ea30b38221b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_sessions",
        sa.Column("voice_agent_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=False),
        sa.Column("transcript", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_credits", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("is_debug", sa.Boolean(), nullable=False),
        sa.Column("end_reason", sa.String(length=50), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voice_agent_id"], ["voice_agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_voice_sessions_agent_started",
        "voice_sessions",
        ["voice_agent_id", "started_at"],
    )
    op.create_index("ix_voice_sessions_created_at", "voice_sessions", ["created_at"])
    op.create_index("ix_voice_sessions_project_id", "voice_sessions", ["project_id"])
    op.create_index("ix_voice_sessions_voice_agent_id", "voice_sessions", ["voice_agent_id"])

    op.add_column(
        "executions",
        sa.Column(
            "voice_session_id",
            sa.Uuid(),
            nullable=True,
            comment="Voice session whose analysis hook started this execution",
        ),
    )
    op.create_index("ix_executions_voice_session_id", "executions", ["voice_session_id"])
    op.create_foreign_key(
        "fk_executions_voice_session_id",
        "executions",
        "voice_sessions",
        ["voice_session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_executions_voice_session_id", "executions", type_="foreignkey")
    op.drop_index("ix_executions_voice_session_id", table_name="executions")
    op.drop_column("executions", "voice_session_id")

    op.drop_index("ix_voice_sessions_voice_agent_id", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_project_id", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_created_at", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_agent_started", table_name="voice_sessions")
    op.drop_table("voice_sessions")
