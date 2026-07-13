"""Authenticated request context shared between the auth dependency and services."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from assemblix_api.database.models.user import User


@dataclass(frozen=True)
class AuthContext:
    """Who is calling and, for API keys, which single project they are scoped to.

    ``scoped_project_id`` is the API key's project for ``sk_`` tokens, or ``None``
    for JWT callers (who may access any project their organization allows).
    """

    user: User
    scoped_project_id: UUID | None
