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


async def test_call_records_transcript_hooks_and_cost(
    db_session: Any, auth_user: Any, voice_session_service: VoiceSessionService
) -> None:
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
    voice_session_id = await voice_session_service.open_session(
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
    await voice_session_service.close_session(
        voice_session_id=voice_session_id,
        transcript=runtime.transcript,
        duration_sec=7.3,
        end_reason=end_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_per_minute=COST_PER_MINUTE,
        uses_system_key=True,
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
    # Billed by wall-clock, not tokens: the $0.02/min platform fee plus provider
    # margin, converted to credits and quantized to what Numeric(20, 8) holds.
    # Also the pin on credits staying a JSON float: the value written is the value read.
    assert str(stored.total_credits) == "64.48333333"
    assert float(stored.total_credits) == 64.48333333

    refreshed = await VoiceAgentRepository(db_session).get_by_id(agent.id)
    assert refreshed is not None
    assert refreshed.session_count == 1
    assert float(refreshed.total_credits) == 64.48333333


async def test_client_id_reaches_the_row_and_every_hook(
    db_session: Any, auth_user: Any, voice_session_service: VoiceSessionService
) -> None:
    """A call opened for a client stamps that client on its row and on every analysis
    hook it starts, so the conversation and its scoring runs share one ClientSession."""
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
    voice_session_id = await voice_session_service.open_session(
        voice_agent_id=agent.id,
        project_id=auth_user.project_id,
        client_id="crm-user-42",
    )

    runner = _RecordingRunner()
    dispatcher = TurnDispatcher(
        voice_session_id=voice_session_id,
        turn_workflow_id=TURN_WORKFLOW_ID,
        final_workflow_id=FINAL_WORKFLOW_ID,
        client_id="crm-user-42",
        runner=runner,
    )

    # Act — the first hook raises on purpose; the client must still travel with it.
    dispatcher.dispatch_turn(user_text="Здравствуйте", agent_reply=None, turn_index=0)
    dispatcher.dispatch_turn(user_text="Запишите меня", agent_reply="Слушаю", turn_index=1)
    await asyncio.sleep(0)
    await dispatcher.dispatch_final(
        transcript=[{"role": "user", "text": "Здравствуйте"}],
        duration_sec=7.3,
        end_reason="user_hangup",
    )

    # Assert
    assert len(runner.calls) == 3
    assert all(call["input_data"]["client_id"] == "crm-user-42" for call in runner.calls)

    stored = await VoiceSessionRepository(db_session).get_by_id(voice_session_id)
    assert stored is not None
    assert stored.client_id == "crm-user-42"


async def test_session_token_round_trips_the_client_id() -> None:
    """The client is sealed into the session token, so the WebSocket — which carries
    no body — still knows which client the call belongs to."""
    # Arrange
    from uuid import uuid4

    from assemblix_api.realtime.session_token import mint_session_token, verify_session_token

    agent_id, project_id = uuid4(), uuid4()

    # Act
    with_client = verify_session_token(
        mint_session_token(
            voice_agent_id=agent_id,
            project_id=project_id,
            is_debug=False,
            client_id="crm-user-42",
        )
    )
    without_client = verify_session_token(
        mint_session_token(voice_agent_id=agent_id, project_id=project_id, is_debug=False)
    )

    # Assert
    assert with_client.client_id == "crm-user-42"
    assert without_client.client_id is None


async def test_client_page_lists_the_calls_of_that_client(
    db_session: Any,
    client: Any,
    auth_user: Any,
    auth_headers: dict,
    voice_session_service: VoiceSessionService,
) -> None:
    """The client's page lists that client's calls and nobody else's — including a call
    that never started a hook, since the stamp is on the call rather than on a run."""
    # Arrange
    agent = await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id,
        name="Receptionist",
        config={
            "instructions": [{"role": "system", "content": "Answer calls."}],
            "voice": {"provider": "openai", "model": "gpt-realtime-2.1", "voiceId": "alloy"},
        },
    )
    mine = await voice_session_service.open_session(
        voice_agent_id=agent.id, project_id=auth_user.project_id, client_id="crm-user-42"
    )
    await voice_session_service.open_session(
        voice_agent_id=agent.id, project_id=auth_user.project_id, client_id="crm-user-99"
    )
    await voice_session_service.open_session(
        voice_agent_id=agent.id, project_id=auth_user.project_id
    )

    # Act
    response = await client.get(
        f"/api/projects/{auth_user.project_id}/client-sessions/crm-user-42/voice-sessions",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["data"]] == [str(mine)]
    assert body["data"][0]["clientId"] == "crm-user-42"
