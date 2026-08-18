# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""A voice call end to end: concurrency ceiling, stale-slot release, and charging."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import HTTPException

from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.database.repositories.voice_session_repository import VoiceSessionRepository
from assemblix_api.enums import PlanTier

# gpt-realtime-2.1, from the voice catalog. The runtime reads it off the resolved
# setup; here it is passed straight in, so the charge is pinned to a known price.
_COST_PER_MINUTE = 0.0576


@pytest_asyncio.fixture
async def voice_session_repository(db_session: Any) -> VoiceSessionRepository:
    """VoiceSessionRepository over the per-test transactional session."""
    return VoiceSessionRepository(db_session)


@pytest_asyncio.fixture
async def voice_setup(
    billing_enabled: Any, db_session: Any, auth_user: Any, voice_session_service: Any
) -> SimpleNamespace:
    """A Free-plan org (one concurrent call) owning one priced voice agent.

    ``open()`` and ``close()`` drive ``VoiceSessionService`` the way the WebSocket
    handler does — open before any audio flows, close once with what the call cost.
    """
    org_repo = OrganizationRepository(db_session)
    organization = await org_repo.get_by_id(auth_user.organization_id)
    # Explicit plan — never rely on the default (BUSINESS while billing is disabled).
    await org_repo.update(organization, plan=PlanTier.FREE)

    agent = await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id,
        name="Receptionist",
        config={
            "instructions": [{"role": "system", "content": "Answer calls."}],
            "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
        },
    )

    async def open_() -> UUID:
        return await voice_session_service.open_session(
            voice_agent_id=agent.id, project_id=auth_user.project_id
        )

    async def close_(voice_session_id: UUID, *, duration_sec: float) -> None:
        await voice_session_service.close_session(
            voice_session_id=voice_session_id,
            transcript=[],
            duration_sec=duration_sec,
            end_reason="user_hangup",
            input_tokens=0,
            output_tokens=0,
            cost_per_minute=_COST_PER_MINUTE,
            uses_system_key=True,
        )

    return SimpleNamespace(organization_id=auth_user.organization_id, open=open_, close=close_)


async def test_voice_call_is_capped_and_charged(
    voice_setup: SimpleNamespace,
    credit_service: Any,
    organization_repository: Any,
    voice_session_repository: VoiceSessionRepository,
) -> None:
    """One-call plan admits one live call, frees a stale slot, and charges on close."""
    # Arrange
    org_id = voice_setup.organization_id
    await organization_repository.reissue_granted_credits(
        org_id, Decimal("500000"), period_start=None
    )
    first_id = await voice_setup.open()

    # Act 1: a second call while the first is still live.
    with pytest.raises(HTTPException) as second:
        await voice_setup.open()

    # Assert 1: the Free plan's single slot is taken.
    assert second.value.status_code == 429

    # Act 2: strand the first call past the cutoff, then dial again and hang up.
    stale = await voice_session_repository.get_by_id(first_id)
    await voice_session_repository.update(stale, started_at=datetime.now(UTC) - timedelta(hours=6))
    third_id = await voice_setup.open()
    await voice_setup.close(third_id, duration_sec=120.0)

    # Assert 2: the stranded row no longer holds the slot, and the call was billed.
    assert third_id is not None

    transactions, _ = await credit_service.get_transactions(org_id)
    charged = {t["type"]: Decimal(str(t["amount_credits"])) for t in transactions}
    # 2 minutes x $0.02/min platform fee, charged whatever key the call ran on.
    assert charged[CreditTransactionType.REQUEST_FEE.value] == Decimal("-400")
    # 2 minutes x $0.0576/min provider cost x 1.1 margin, because it ran on our key.
    assert charged[CreditTransactionType.VOICE_USAGE.value] == Decimal("-1267.2")

    org = await organization_repository.get_by_id(org_id)
    assert org.credits_granted_balance == Decimal("500000") - Decimal("1667.2")
