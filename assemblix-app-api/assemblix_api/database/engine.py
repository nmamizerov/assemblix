"""
Database engine and session management
"""

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Session

from assemblix_api.core.settings import get_settings

settings = get_settings()

# Sync engine (Alembic migrations and startup health-check).
engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # Validate connection liveness before checkout.
    pool_recycle=3600,  # Recycle connections every hour to avoid stale TCP.
    pool_timeout=settings.db_pool_timeout,  # Seconds to wait for a free slot.
)

# Async engine for runtime operations; rewrite the driver to asyncpg.
async_database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

async_engine: AsyncEngine | None = None


def get_async_engine() -> AsyncEngine:
    """Return the lazily-created async engine."""
    global async_engine
    if async_engine is None:
        connect_args: dict = {}
        if settings.db_disable_statement_cache:
            # Behind a transaction-mode pooler (PgBouncer/Supavisor) prepared statements
            # break (DuplicatePreparedStatement / InvalidSQLStatementName) because server
            # connections are multiplexed. Two caches must be disabled to be pooler-safe:
            #   statement_cache_size=0          → asyncpg's own prepared-statement cache.
            #   prepared_statement_cache_size=0 → SQLAlchemy's asyncpg dialect cache, which
            #     otherwise reuses a prepared statement across transactions (i.e. across
            #     different multiplexed server backends) and fails. SQLAlchemy pops this
            #     key from connect_args before calling asyncpg.connect.
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0
        async_engine = create_async_engine(
            async_database_url,
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_timeout=settings.db_pool_timeout,  # Seconds to wait for a free slot.
            connect_args=connect_args,
        )
    return async_engine


def get_session() -> Generator[Session]:
    """
    Sync database session (used by migrations).

    DEPRECATED: use get_async_session for runtime operations.
    """
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """
    Async database session for use as a FastAPI dependency.

    Manages the session lifecycle automatically (commit on success,
    rollback on exception).

    Example:
        ```python
        from fastapi import Depends
        from assemblix_api.database import get_async_session

        @router.get("/users/{user_id}")
        async def get_user(
            user_id: UUID,
            session: AsyncSession = Depends(get_async_session)
        ):
            user = await session.get(User, user_id)
            return user
        ```
    """
    engine = get_async_engine()
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def check_db_connection() -> bool:
    """Check the database connection synchronously (for startup checks)."""
    try:
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_async_db_connection() -> bool:
    """Check the database connection asynchronously."""
    try:
        engine = get_async_engine()
        async with AsyncSession(engine) as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
