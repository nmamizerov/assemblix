"""fix_executionstatus_enum

Revision ID: f03e23f487d0
Revises: c030bb311591
Create Date: 2026-02-03 14:37:15.982920

Добавляет значение 'ERROR' в enum executionstatus
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f03e23f487d0"
down_revision = "c030bb311591"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем значение 'ERROR' в существующий enum
    op.execute("ALTER TYPE executionstatus ADD VALUE 'ERROR'")


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значений из enum
    # Нужно пересоздать тип без 'ERROR'
    op.execute(
        """
        CREATE TYPE executionstatus_old AS ENUM ('RUNNING', 'COMPLETED', 'FAILED')
    """
    )

    # Конвертируем ERROR -> FAILED при откате
    op.execute(
        """
        ALTER TABLE executions 
        ALTER COLUMN status TYPE executionstatus_old 
        USING (
            CASE status::text
                WHEN 'ERROR' THEN 'FAILED'::executionstatus_old
                ELSE status::text::executionstatus_old
            END
        )
    """
    )

    op.execute("DROP TYPE executionstatus")
    op.execute("ALTER TYPE executionstatus_old RENAME TO executionstatus")
