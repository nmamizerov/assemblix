"""Shared helper for resolving the effective project of a request.

Endpoints that historically required an explicit ``project_id`` (built for the
JWT frontend, where one user spans many projects) can accept it optionally: when
omitted, a project-scoped API key supplies its own project. JWT callers, which
carry no scoped project, must still pass one.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.core.auth_context import AuthContext


def resolve_project_id(explicit: UUID | None, auth: AuthContext) -> UUID:
    """Return the explicit project_id, else the API key's scoped project.

    Raises 400 when neither is available (e.g. a JWT caller that omitted it).
    """
    effective = explicit or auth.scoped_project_id
    if effective is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id is required unless using a project-scoped API key",
        )
    return effective
