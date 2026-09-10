"""A call placed on the caller's own provider key still has a real dollar cost."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from assemblix_api.services.voice_session_service import VoiceSessionService


def _service(session, agent) -> tuple[VoiceSessionService, AsyncMock, AsyncMock]:
    sessions = AsyncMock()
    sessions.get_by_id.return_value = session
    voice_agents = AsyncMock()
    voice_agents.get_by_id.return_value = agent
    service = VoiceSessionService(
        voice_agents=voice_agents,
        projects=AsyncMock(),
        organizations=AsyncMock(),
        knowledge_bases=AsyncMock(),
        credentials=AsyncMock(),
        sessions=sessions,
        transactions=AsyncMock(),
        credits=AsyncMock(),
    )
    return service, sessions, voice_agents


async def _close(*, uses_system_key: bool):
    session = SimpleNamespace(
        id=uuid4(), voice_agent_id=uuid4(), project_id=uuid4(), transcript=[]
    )
    agent = SimpleNamespace(
        session_count=2, total_credits=Decimal("5"), own_key_cost_usd=Decimal("0.5")
    )
    service, sessions, voice_agents = _service(session, agent)
    await service.close_session(
        voice_session_id=session.id,
        transcript=[],
        duration_sec=120.0,
        end_reason="user_hangup",
        input_tokens=10,
        output_tokens=20,
        cost_per_minute=0.30,
        uses_system_key=uses_system_key,
    )
    return sessions.update.await_args.kwargs, voice_agents.update.await_args.kwargs


@pytest.mark.asyncio
async def test_own_key_call_records_provider_cost() -> None:
    """Two minutes at $0.30/min on an own key is $0.60 — recorded, not dropped."""
    # Arrange / Act
    session_update, agent_update = await _close(uses_system_key=False)
    # Assert
    assert session_update["own_key_cost_usd"] == Decimal("0.60")
    assert agent_update["own_key_cost_usd"] == Decimal("1.10")


@pytest.mark.asyncio
async def test_system_key_call_records_no_own_cost() -> None:
    """On a system key the user pays in credits, so the own-key figure stays zero."""
    # Arrange / Act
    session_update, agent_update = await _close(uses_system_key=True)
    # Assert
    assert session_update["own_key_cost_usd"] == Decimal("0")
    assert agent_update["own_key_cost_usd"] == Decimal("0.5")
