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

# What a two-minute call on our keys costs: 2 x $0.02/min platform fee, plus
# 2 x $0.0576/min provider cost at the 1.1 margin, both in credits ($0.0001 each).
_FEE_CREDITS = Decimal("400")
_MARGIN_CREDITS = Decimal("1267.2")


def _credits_by_type(transactions: list[dict]) -> dict[str, list[Decimal]]:
    """Charged amounts per transaction type, oldest first."""
    by_type: dict[str, list[Decimal]] = {}
    for tx in reversed(transactions):
        by_type.setdefault(tx["type"], []).append(Decimal(str(tx["amount_credits"])))
    return by_type


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
    charged = _credits_by_type(transactions)
    # The platform fee is charged whatever key the call ran on...
    assert charged[CreditTransactionType.REQUEST_FEE.value] == [-_FEE_CREDITS]
    # ...the provider margin only because this one ran on our key.
    assert charged[CreditTransactionType.VOICE_USAGE.value] == [-_MARGIN_CREDITS]

    org = await organization_repository.get_by_id(org_id)
    assert org.credits_balance == Decimal("500000") - _FEE_CREDITS - _MARGIN_CREDITS

    # Act 3: a balance that clears the floor to start a call but cannot pay for it.
    await organization_repository.reissue_granted_credits(org_id, Decimal("300"), period_start=None)
    fourth_id = await voice_setup.open()
    await voice_setup.close(fourth_id, duration_sec=120.0)

    # Act 4: dial again on what that call left behind.
    with pytest.raises(HTTPException) as fifth:
        await voice_setup.open()

    # Assert 3: the overdrawn call took everything there was and recorded the rest,
    # which puts the account under the floor — so it gets no second free call.
    org = await organization_repository.get_by_id(org_id)
    assert org.credits_balance == Decimal("0")
    assert fifth.value.status_code == 402

    transactions, _ = await credit_service.get_transactions(org_id)
    charged = _credits_by_type(transactions)
    # The 300 on hand went to the fee first, so the margin bought nothing.
    assert charged[CreditTransactionType.REQUEST_FEE.value] == [-_FEE_CREDITS, Decimal("-300")]
    assert charged[CreditTransactionType.VOICE_USAGE.value] == [-_MARGIN_CREDITS]
    unpaid = [t["metadata"]["shortfall_credits"] for t in transactions]
    assert sorted(unpaid) == [0.0, 0.0, float(_FEE_CREDITS + _MARGIN_CREDITS - Decimal("300"))]
