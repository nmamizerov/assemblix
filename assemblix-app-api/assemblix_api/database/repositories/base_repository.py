"""Generic base repository for CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):  # noqa: UP046 — keep explicit TypeVar (module-level ModelType reused below)
    """
    Base repository with CRUD operations.

    Usage:
        class UserRepository(BaseRepository[User]):
            pass
    """

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self._model = model
        self._session = session

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Return a record by ID."""
        stmt = select(self._model).where(self._model.id == id)  # type: ignore[attr-defined]  # id provided by UUIDMixin on all concrete models
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> Sequence[ModelType]:
        """Return paginated records (defaults to created_at desc ordering)."""
        stmt = select(self._model)

        if order_by:
            stmt = stmt.order_by(getattr(self._model, order_by))
        elif hasattr(self._model, "created_at"):
            stmt = stmt.order_by(self._model.created_at.desc())  # type: ignore[attr-defined]  # created_at provided by TimestampMixin on concrete models

        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        """Return the total number of records."""
        stmt = select(func.count()).select_from(self._model)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        """Update an existing record instance with the given fields."""
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, id: UUID) -> bool:
        """Delete a record by ID. Returns True if a row was deleted."""
        stmt = delete(self._model).where(self._model.id == id)  # type: ignore[attr-defined]  # id provided by UUIDMixin on all concrete models
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0  # type: ignore[attr-defined]  # rowcount available on CursorResult for DML statements

    async def delete_instance(self, instance: ModelType) -> None:
        """Delete a model instance."""
        await self._session.delete(instance)
        await self._session.flush()

    async def exists(self, id: UUID) -> bool:
        """Check whether a record with the given ID exists."""
        stmt = select(func.count()).select_from(self._model).where(self._model.id == id)  # type: ignore[attr-defined]  # id provided by UUIDMixin on all concrete models
        result = await self._session.execute(stmt)
        count = result.scalar_one()
        return count > 0
