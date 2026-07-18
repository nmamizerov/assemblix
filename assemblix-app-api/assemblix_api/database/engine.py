"""
Database engine and session management
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Session

from assemblix_api.core.settings import get_settings

settings = get_settings()


class SerializedAsyncSession(AsyncSession):
    """AsyncSession that serializes DB operations across concurrent asyncio tasks.

    A workflow run shares one session across every branch. On the parallel engine,
    fork branches run as concurrent tasks, so two branches may `await` the DB at the
    same instant — which a stock AsyncSession forbids ("This session is provisioning a
    new connection; concurrent operations are not permitted").

    A per-task *reentrant* lock guards the coroutine methods that actually touch the
    connection. Reentrancy is required because some methods call others through the
    async facade (`scalar`/`scalars` → `execute`, `stream_scalars` → `stream`); a plain
    lock would deadlock within a single task. Cross-task calls serialize on the DB touch
    only — the expensive awaits between DB calls (LLM/HTTP) still overlap, and the single
    transaction / node-boundary checkpoint semantics are unchanged.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._db_lock = asyncio.Lock()
        self._db_lock_owner: asyncio.Task | None = None
        self._db_lock_depth = 0

    @asynccontextmanager
    async def _serialized(self) -> AsyncIterator[None]:
        task = asyncio.current_task()
        if self._db_lock_owner is task and task is not None:
            # Nested DB call within the branch that already holds the lock.
            self._db_lock_depth += 1
            try:
                yield
            finally:
                self._db_lock_depth -= 1
            return
        await self._db_lock.acquire()
        self._db_lock_owner = task
        self._db_lock_depth = 1
        try:
            yield
        finally:
            self._db_lock_depth -= 1
            if self._db_lock_depth == 0:
                self._db_lock_owner = None
                self._db_lock.release()

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().execute(*args, **kwargs)

    async def scalar(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().scalar(*args, **kwargs)

    async def scalars(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().scalars(*args, **kwargs)

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().stream(*args, **kwargs)

    async def stream_scalars(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().stream_scalars(*args, **kwargs)

    async def get(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().get(*args, **kwargs)

    async def get_one(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().get_one(*args, **kwargs)

    async def refresh(self, *args: Any, **kwargs: Any) -> None:
        async with self._serialized():
            await super().refresh(*args, **kwargs)

    async def merge(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().merge(*args, **kwargs)

    async def delete(self, *args: Any, **kwargs: Any) -> None:
        async with self._serialized():
            await super().delete(*args, **kwargs)

    async def flush(self, *args: Any, **kwargs: Any) -> None:
        async with self._serialized():
            await super().flush(*args, **kwargs)

    async def commit(self) -> None:
        async with self._serialized():
            await super().commit()

    async def rollback(self) -> None:
        async with self._serialized():
            await super().rollback()

    async def connection(self, *args: Any, **kwargs: Any) -> Any:
        async with self._serialized():
            return await super().connection(*args, **kwargs)

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
