"""add deepseek and gigachat credentials types

Revision ID: f5a6b7c8d9e0
Revises: 3a68f08bcc0d
Create Date: 2026-01-02 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f5a6b7c8d9e0"
down_revision = "3a68f08bcc0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Добавляет новые типы credentials: DEEPSEEK_TOKEN и GIGACHAT_TOKEN
    в enum credentialstype
    """
    # PostgreSQL requires ALTER TYPE ... ADD VALUE to be executed outside of transaction
    # Alembic's op.execute() handles this correctly

    # Add DEEPSEEK_TOKEN to enum
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'DEEPSEEK_TOKEN'")

    # Add GIGACHAT_TOKEN to enum
    op.execute("ALTER TYPE credentialstype ADD VALUE IF NOT EXISTS 'GIGACHAT_TOKEN'")


def downgrade() -> None:
    """
    Откат изменений: удаление новых типов из enum

    ВАЖНО: В PostgreSQL невозможно удалить значение из enum напрямую.
    Для отката нужно:
    1. Создать новый enum без удаляемых значений
    2. Конвертировать колонку в новый тип
    3. Удалить старый enum
    4. Переименовать новый enum

    Это сложная операция, поэтому в production рекомендуется не откатывать
    такие миграции, а создавать новые для исправления.
    """

    # Проверяем, есть ли записи с новыми типами
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM credentials "
            "WHERE type IN ('DEEPSEEK_TOKEN', 'GIGACHAT_TOKEN')"
        )
    )
    count = result.scalar()

    if count > 0:
        raise Exception(
            f"Cannot downgrade: {count} credentials with DEEPSEEK_TOKEN or GIGACHAT_TOKEN exist. "
            "Please delete or migrate these credentials first."
        )

    # Создаем новый enum без новых значений
    op.execute(
        """
        CREATE TYPE credentialstype_new AS ENUM (
            'OPENAI_TOKEN',
            'ANTHROPIC_TOKEN',
            'GEMINI_TOKEN'
        )
        """
    )

    # Конвертируем колонку в новый тип
    op.execute(
        """
        ALTER TABLE credentials 
        ALTER COLUMN type TYPE credentialstype_new 
        USING type::text::credentialstype_new
        """
    )

    # Удаляем старый enum
    op.execute("DROP TYPE credentialstype")

    # Переименовываем новый enum
    op.execute("ALTER TYPE credentialstype_new RENAME TO credentialstype")
