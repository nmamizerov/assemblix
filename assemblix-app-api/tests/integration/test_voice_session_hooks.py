"""One whole call: transcript persisted, hooks dispatched, cost written.

Driven by a fake bridge — the realtime equivalent of the LLM mock seam. Nothing here
talks to a provider, and the hook workflows are replaced by a recording runner, so
what is under test is the wiring between the runtime, the dispatcher and the
``voice_sessions`` row rather than the graph engine.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from assemblix_api.database.repositories.credentials_repository import CredentialsRepository
from assemblix_api.database.repositories.knowledge_base_repository import KnowledgeBaseRepository
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
from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    SessionClosed,
    TurnEnded,
    UserTranscript,
)
from assemblix_api.realtime.hooks import TurnDispatcher
from assemblix_api.realtime.runtime import VoiceSessionRuntime
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService
from assemblix_api.services.voice_session_service import VoiceSessionService

TURN_WORKFLOW_ID = "11111111-1111-1111-1111-111111111111"
FINAL_WORKFLOW_ID = "22222222-2222-2222-2222-222222222222"
# The Gemini Live catalog price; chosen so the cost needs all eight decimals.
COST_PER_MINUTE = 0.03


class _FakeBridge:
    """Replays a two-turn conversation and then hangs up."""

    input_sample_rate = 24000
    output_sample_rate = 24000

    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def connect(self, **kwargs: Any) -> None: ...

    async def send_audio(self, pcm: bytes) -> None: ...

    async def interrupt(self, *, audio_end_ms: int) -> None: ...

    def events(self) -> AsyncIterator[Any]:
        async def _iter() -> AsyncIterator[Any]:
            for event in self._events:
                yield event

        return _iter()

    async def close(self) -> None: ...


class _FakeClient:
    def __init__(self) -> None:
        self.json_frames: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.json_frames.append(data)

    async def send_bytes(self, data: bytes) -> None: ...

    async def __aiter__(self) -> AsyncIterator[Any]:
        # The browser says nothing; the provider drives this call to its end.
        await asyncio.sleep(3600)
        yield b""


class _RecordingRunner:
    """Stands in for run_workflow_isolated. The first turn hook fails on purpose."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise RuntimeError("hook exploded")


def _service(db_session: Any) -> VoiceSessionService:
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
    )


async def test_call_records_transcript_hooks_and_cost(db_session: Any, auth_user: Any) -> None:
    """A finished call leaves behind its transcript, its cost, and one hook run per
    user utterance — and a hook that raises neither ends the call nor is awaited."""
    # Arrange
    agent = await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id,
        name="Receptionist",
        config={
            "instructions": [{"role": "system", "content": "Answer calls."}],
            "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
            "turnWorkflowId": TURN_WORKFLOW_ID,
            "finalWorkflowId": FINAL_WORKFLOW_ID,
        },
    )
    service = _service(db_session)
    voice_session_id = await service.open_session(
        voice_agent_id=agent.id, project_id=auth_user.project_id
    )

    runner = _RecordingRunner()
    runtime = VoiceSessionRuntime(
        bridge=_FakeBridge(
            [
                UserTranscript(text="Здравствуйте", is_final=True),
                AgentTranscript(text="Здравствуйте, слушаю", is_final=True),
                TurnEnded(input_tokens=120, output_tokens=45),
                UserTranscript(text="Запишите меня", is_final=False),
                UserTranscript(text="Запишите меня на приём", is_final=True),
                TurnEnded(input_tokens=80, output_tokens=30),
                SessionClosed(reason="user_hangup"),
            ]
        ),
        client=_FakeClient(),
        instructions="Answer calls.",
        voice="alloy",
        language="ru",
        params={},
        max_session_sec=5,
        dispatcher=TurnDispatcher(
            voice_session_id=voice_session_id,
            turn_workflow_id=TURN_WORKFLOW_ID,
            final_workflow_id=FINAL_WORKFLOW_ID,
            runner=runner,
        ),
    )

    # Act
    end_reason = await runtime.run()
    # Per-turn hooks are fired and never awaited, so let the loop drain them.
    await asyncio.sleep(0)
    input_tokens, output_tokens = runtime.usage
    await service.close_session(
        voice_session_id=voice_session_id,
        transcript=runtime.transcript,
        duration_sec=7.3,
        end_reason=end_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_per_minute=COST_PER_MINUTE,
    )

    # Assert — the call itself survived a hook that raised
    assert end_reason == "user_hangup"

    turn_calls = [c for c in runner.calls if str(c["workflow_id"]) == TURN_WORKFLOW_ID]
    final_calls = [c for c in runner.calls if str(c["workflow_id"]) == FINAL_WORKFLOW_ID]
    assert len(turn_calls) == 2, "one per finalized user utterance, interim ignored"
    assert len(final_calls) == 1, "the final hook runs exactly once"

    assert turn_calls[0]["input_data"]["message"] == "Здравствуйте"
    assert turn_calls[0]["input_data"]["voice"]["turn_index"] == 0
    assert turn_calls[1]["input_data"]["voice"]["agent_reply"] == "Здравствуйте, слушаю"
    assert all(c["voice_session_id"] == voice_session_id for c in runner.calls)
    assert final_calls[0]["input_data"]["voice"]["end_reason"] == "user_hangup"
    assert len(final_calls[0]["input_data"]["voice"]["transcript"]) == 3

    # Assert — the row carries the whole call
    stored = await VoiceSessionRepository(db_session).get_by_id(voice_session_id)
    assert stored is not None
    assert stored.status == "completed"
    assert stored.end_reason == "user_hangup"
    assert [line["text"] for line in stored.transcript] == [
        "Здравствуйте",
        "Здравствуйте, слушаю",
        "Запишите меня на приём",
    ]
    assert (stored.input_tokens, stored.output_tokens) == (200, 75)
    # Billed by wall-clock, not tokens, and quantized to what Numeric(20, 8) holds.
    # Also the pin on credits staying a JSON float: the value written is the value read.
    assert str(stored.total_credits) == "0.00365000"
    assert float(stored.total_credits) == 0.00365

    refreshed = await VoiceAgentRepository(db_session).get_by_id(agent.id)
    assert refreshed is not None
    assert refreshed.session_count == 1
    assert float(refreshed.total_credits) == 0.00365
