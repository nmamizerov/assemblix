"""Voice fixtures: a ``VoiceSessionService`` wired over the per-test session.

Registered as a plugin from ``tests/conftest.py`` (``pytest_plugins``). The service
has no FastAPI dependency chain to hang off — it is composed explicitly — so both
the call-lifecycle and the billing tests would otherwise each carry their own copy
of this wiring.
"""

from __future__ import annotations

from typing import Any

import pytest_asyncio


@pytest_asyncio.fixture
async def voice_session_service(db_session: Any) -> Any:
    """VoiceSessionService with every repository bound to the transactional session."""
    from assemblix_api.database.repositories.credentials_repository import CredentialsRepository
    from assemblix_api.database.repositories.credit_transaction_repository import (
        CreditTransactionRepository,
    )
    from assemblix_api.database.repositories.knowledge_base_repository import (
        KnowledgeBaseRepository,
    )
    from assemblix_api.database.repositories.knowledge_document_repository import (
        KnowledgeDocumentRepository,
    )
    from assemblix_api.database.repositories.organization_repository import OrganizationRepository
    from assemblix_api.database.repositories.organization_user_repository import (
        OrganizationUserRepository,
    )
    from assemblix_api.database.repositories.project_repository import ProjectRepository
    from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
    from assemblix_api.database.repositories.voice_session_repository import VoiceSessionRepository
    from assemblix_api.services.credentials_service import CredentialsService
    from assemblix_api.services.knowledge_base_service import KnowledgeBaseService
    from assemblix_api.services.voice_session_service import VoiceSessionService

    return VoiceSessionService(
        VoiceAgentRepository(db_session),
        ProjectRepository(db_session),
        OrganizationRepository(db_session),
        KnowledgeBaseService(
            KnowledgeBaseRepository(db_session), KnowledgeDocumentRepository(db_session)
        ),
        CredentialsService(
            CredentialsRepository(db_session), OrganizationUserRepository(db_session)
        ),
        VoiceSessionRepository(db_session),
        CreditTransactionRepository(db_session),
    )
