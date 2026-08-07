"""Gemini Live event normalization — the seam's second implementation.

The adapter is the only place allowed to know that this provider streams
transcription in fragments, announces barge-in after the fact, and ends its
receive() iterator on every turn. Everything above it sees the same BridgeEvent
vocabulary OpenAI produces.
"""

from __future__ import annotations

from typing import Any

from google.genai import types

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)
from assemblix_api.external.voice.conversation.gemini import GeminiLiveBridge


def _message(
    *,
    input_text: str | None = None,
    input_done: bool = False,
    output_text: str | None = None,
    output_done: bool = False,
    audio: bytes | None = None,
    interrupted: bool = False,
    turn_complete: bool = False,
    usage: tuple[int, int] | None = None,
) -> types.LiveServerMessage:
    content = types.LiveServerContent(
        input_transcription=(
            types.Transcription(text=input_text, finished=input_done)
            if input_text is not None
            else None
        ),
        output_transcription=(
            types.Transcription(text=output_text, finished=output_done)
            if output_text is not None
            else None
        ),
        model_turn=(
            types.Content(parts=[types.Part(inline_data=types.Blob(data=audio))])
            if audio is not None
            else None
        ),
        interrupted=interrupted or None,
        turn_complete=turn_complete or None,
    )
    return types.LiveServerMessage(
        server_content=content,
        usage_metadata=(
            types.UsageMetadata(prompt_token_count=usage[0], response_token_count=usage[1])
            if usage
            else None
        ),
    )


class _FakeSession:
    """One turn of provider frames, then an exhausted iterator — the real SDK's
    receive() also ends after every turn_complete."""

    def __init__(self, messages: list[Any]) -> None:
        self._turns = [messages, []]

    async def receive(self):
        for message in self._turns.pop(0) if self._turns else []:
            yield message


async def test_provider_frames_become_bridge_events() -> None:
    """Fragmented transcription is accumulated and finalized by the adapter — this
    provider never flags an utterance as finished, so the caller's line is closed off
    when the agent starts answering, and the agent's when the turn ends or is cut off.
    Barge-in becomes SpeechStarted without losing what was already said."""
    # Arrange
    session = _FakeSession(
        [
            _message(input_text="Запишите "),
            _message(input_text="меня"),
            _message(audio=b"\x01\x02"),
            _message(output_text="Конечно"),
            _message(interrupted=True),
            _message(output_text="Записал"),
            _message(turn_complete=True, usage=(120, 45)),
        ]
    )
    bridge = GeminiLiveBridge(
        api_key="k",
        model="gemini-3.1-flash-live-preview",
        connect_factory=lambda **_: session,
    )
    await bridge.connect(instructions="Answer calls.", voice="Puck", language="ru", params={})

    # Act
    events = [event async for event in bridge.events()]

    # Assert
    assert events == [
        UserTranscript(text="Запишите ", is_final=False),
        UserTranscript(text="Запишите меня", is_final=False),
        # The agent's first audio ends the caller's utterance: nothing else will.
        UserTranscript(text="Запишите меня", is_final=True),
        AudioDelta(pcm=b"\x01\x02"),
        AgentTranscript(text="Конечно", is_final=False),
        # Interrupted mid-word — but "Конечно" was spoken, so it is kept.
        SpeechStarted(),
        AgentTranscript(text="Конечно", is_final=True),
        AgentTranscript(text="Записал", is_final=False),
        AgentTranscript(text="Записал", is_final=True),
        TurnEnded(input_tokens=120, output_tokens=45),
        SessionClosed(reason="closed"),
    ]
    assert bridge.input_sample_rate == 16000, "Gemini listens at 16kHz, unlike OpenAI"
    assert bridge.output_sample_rate == 24000
