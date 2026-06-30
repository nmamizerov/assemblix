"""Workflow repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.models.workflow import Workflow
from assemblix_api.database.repositories.base_repository import BaseRepository


class WorkflowRepository(BaseRepository[Workflow]):
    """Repository for the workflows table."""

    def __init__(self, session: AsyncSession):
        super().__init__(Workflow, session)

    async def get_by_slug(self, slug: str) -> Workflow | None:
        """Get a workflow by slug."""
        stmt = select(self._model).where(self._model.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_project_id(
        self,
        project_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
        is_published: bool | None = None,
        is_template: bool | None = None,
        only_drafts: bool = True,
    ) -> Sequence[Workflow]:
        """Get all workflows for a project with filtering.

        When only_drafts is True (default), returns only editable drafts.
        """
        stmt = select(self._model).where(self._model.project_id == project_id)

        if only_drafts:
            stmt = stmt.where(self._model.published_for_workflow_id.is_(None))

        if is_active is not None:
            stmt = stmt.where(self._model.is_active == is_active)
        if is_published is not None:
            stmt = stmt.where(self._model.is_published == is_published)
        if is_template is not None:
            stmt = stmt.where(self._model.is_template == is_template)

        stmt = stmt.order_by(self._model.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def check_project_owns_workflow(self, workflow_id: UUID, project_id: UUID) -> bool:
        """Check whether a workflow belongs to a project."""
        stmt = select(self._model).where(
            self._model.id == workflow_id, self._model.project_id == project_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_latest_published(self, workflow_id: UUID) -> Workflow | None:
        """Get the latest published version of a workflow."""
        stmt = (
            select(self._model)
            .where(self._model.published_for_workflow_id == workflow_id)
            .order_by(self._model.version.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_next_version(self, workflow_id: UUID) -> int:
        """Get the next version number for a workflow (1 for the first publication)."""
        latest = await self.get_latest_published(workflow_id)
        if latest and latest.version is not None:
            return latest.version + 1
        return 1

    async def get_published_versions(self, workflow_id: UUID) -> Sequence[Workflow]:
        """Get all published versions of a workflow, ordered by version descending."""
        stmt = (
            select(self._model)
            .where(self._model.published_for_workflow_id == workflow_id)
            .order_by(self._model.version.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def move_to_project(self, workflow_id: UUID, target_project_id: UUID) -> None:
        """Move a workflow and all its published versions to another project."""
        stmt = (
            update(self._model)
            .where(
                or_(
                    self._model.id == workflow_id,
                    self._model.published_for_workflow_id == workflow_id,
                )
            )
            .values(project_id=target_project_id)
        )
        await self._session.execute(stmt)

    async def count_organization_workflows(
        self, organization_id: UUID, source: str | None = None
    ) -> int:
        """Count workflows (agents) in an organization.

        Counts only drafts (published_for_workflow_id IS NULL), since published
        versions are copies of the same agent.
        """
        from assemblix_api.database.models.project import Project

        stmt = (
            select(func.count())
            .select_from(self._model)
            .join(Project, self._model.project_id == Project.id)
            .where(
                Project.organization_id == organization_id,
                self._model.published_for_workflow_id.is_(None),  # drafts only
            )
        )
        if source is not None:
            stmt = stmt.where(self._model.source == source)
        result = await self._session.execute(stmt)
        return result.scalar_one()
