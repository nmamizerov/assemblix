"""Unit tests for ProjectService.authorize_project_access scope enforcement."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.services.project_service import ProjectService


class _StubRepo:
    def __init__(self, project):
        self._project = project

    async def get_by_id(self, project_id):
        return self._project


def _service(project):
    svc = ProjectService.__new__(ProjectService)
    svc._repository = _StubRepo(project)  # type: ignore[attr-defined]
    return svc


async def test_scoped_key_mismatch_raises_403() -> None:
    # Arrange
    scoped = uuid4()
    other = uuid4()
    project = SimpleNamespace(id=other, organization_id=uuid4())
    svc = _service(project)
    auth = AuthContext(user=SimpleNamespace(id="u"), scoped_project_id=scoped)  # type: ignore[arg-type]

    # Act / Assert
    with pytest.raises(HTTPException) as exc:
        await svc.authorize_project_access(auth, other)
    assert exc.value.status_code == 403
