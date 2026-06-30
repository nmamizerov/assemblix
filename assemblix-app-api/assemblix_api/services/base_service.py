"""Generic base service for CRUD business logic."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.base import Base
from assemblix_api.database.repositories.base_repository import BaseRepository

ModelType = TypeVar("ModelType", bound=Base)
RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)


class BaseService(Generic[ModelType, RepositoryType]):  # noqa: UP046 — keep explicit TypeVars (module-level, reused below)
    """
    Base service with CRUD business logic.

    Usage:
        class WorkflowService(BaseService[Workflow, WorkflowRepository]):
            def __init__(self, repository: WorkflowRepository):
                super().__init__(repository, "Workflow")
    """

    def __init__(self, repository: RepositoryType, entity_name: str = "Entity"):
        self._repository = repository
        self._entity_name = entity_name

    async def get_by_id(self, id: UUID) -> ModelType:
        instance = await self._repository.get_by_id(id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self._entity_name} с ID {id} не найден",
            )
        return instance

    async def get_by_id_or_none(self, id: UUID) -> ModelType | None:
        return await self._repository.get_by_id(id)

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> Sequence[ModelType]:
        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Максимальный лимит - 1000 записей",
            )
        return await self._repository.get_all(skip=skip, limit=limit, order_by=order_by)

    async def count(self) -> int:
        return await self._repository.count()

    async def create(self, **kwargs) -> ModelType:
        return await self._repository.create(**kwargs)

    async def update(self, id: UUID, **kwargs) -> ModelType:
        instance = await self.get_by_id(id)
        return await self._repository.update(instance, **kwargs)

    async def delete(self, id: UUID) -> None:
        if not await self._repository.exists(id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self._entity_name} с ID {id} не найден",
            )
        await self._repository.delete(id)

    async def exists(self, id: UUID) -> bool:
        return await self._repository.exists(id)
