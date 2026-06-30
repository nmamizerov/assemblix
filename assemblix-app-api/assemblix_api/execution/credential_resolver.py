# /execution/credential_resolver.py
"""Resolving the API key for the agent node (extracted from the node).

A thin wrapper over `CredentialsService.get_api_key_with_fallback`: parses
`credential_id` and returns `(api_key, is_system_key)`. Lazy loading at node
execution time (we do not pre-resolve all nodes — branches/loops may not
execute). In Phase 3, a timeout/fallback on resolution will be built in here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from assemblix_api.enums import AgentProvider, PlanTier
    from assemblix_api.services.credentials_service import CredentialsService


class CredentialResolver:
    def __init__(self, credential_service: CredentialsService):
        self._service = credential_service

    async def resolve(
        self,
        *,
        credential_id: str | None,
        provider: AgentProvider,
        project_id: UUID,
        organization_plan: PlanTier,
    ) -> tuple[str, bool]:
        """Return `(api_key, is_system_key)` with a fallback to system keys."""
        credentials_id = UUID(credential_id) if credential_id else None
        return await self._service.get_api_key_with_fallback(
            credentials_id=credentials_id,
            project_id=project_id,
            provider=provider,
            organization_plan=organization_plan,
        )
