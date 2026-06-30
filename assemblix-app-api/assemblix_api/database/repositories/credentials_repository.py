"""Credentials repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.core.encryption import get_encryption_service
from assemblix_api.database.models.credentials import Credentials, CredentialsType
from assemblix_api.database.repositories.base_repository import BaseRepository

logger = structlog.get_logger(__name__)


class CredentialsRepository(BaseRepository[Credentials]):
    """
    Repository for the credentials table.

    Encrypts values on write; does NOT decrypt on read (for security).
    Use get_decrypted_value() to obtain the decrypted value.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(Credentials, session)
        self._encryption_service = get_encryption_service()

    async def create(self, **kwargs) -> Credentials:
        """Create credentials, encrypting the value before storing."""
        if "value" in kwargs and kwargs["value"]:
            kwargs["value"] = self._encryption_service.encrypt(kwargs["value"])

        return await super().create(**kwargs)

    async def update(self, entity_id: UUID, **kwargs) -> Credentials:  # type: ignore[override]  # deliberate id-based update API distinct from base instance-based update
        """Update credentials, encrypting the value if it is being changed."""
        if "value" in kwargs and kwargs["value"]:
            kwargs["value"] = self._encryption_service.encrypt(kwargs["value"])

        return await super().update(entity_id, **kwargs)  # type: ignore[arg-type]  # base update is instance-based; this subclass intentionally passes the id

    async def get_decrypted_value(self, credentials_id: UUID) -> str:
        """
        Return the decrypted credentials value.

        WARNING: backend-internal use only (e.g. calling LLM providers).
        NEVER send the result to the frontend.

        Raises ValueError if missing/empty, InvalidToken if data is corrupted.
        """
        credentials = await self.get_by_id(credentials_id)

        if credentials is None or not credentials.value:
            raise ValueError(f"Credentials {credentials_id} не содержит значения")

        try:
            return self._encryption_service.decrypt(credentials.value)
        except Exception:
            logger.error("credentials.decrypt_failed", credentials_id=str(credentials_id))
            raise

    async def get_by_project_id(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        type: CredentialsType | None = None,
    ) -> Sequence[Credentials]:
        """Return a project's credentials, optionally filtered by provider type."""
        stmt = select(self._model).where(self._model.project_id == project_id)

        if type is not None:
            stmt = stmt.where(self._model.type == type)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def check_project_owns_credentials(self, credentials_id: UUID, project_id: UUID) -> bool:
        """Check whether the credentials belong to the project."""
        stmt = select(self._model).where(
            self._model.id == credentials_id, self._model.project_id == project_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
