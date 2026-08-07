"""The voice session runtime: one asyncio task pumping audio both ways.

Constraints that are not negotiable (see CLAUDE.md):

* it never holds a DB connection — everything it needs is passed in;
* it never goes through the Arq queue — audio lives in process memory;
* it takes no application state, only explicit arguments, so the whole runtime
  can move into its own process later without being rewritten.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from typing import Protocol

import structlog

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    BridgeError,
    RealtimeBridge,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)

logger = structlog.get_logger(__name__)

# Both directions run at the provider's required rate; the browser reaches it
# natively via `new AudioContext({ sampleRate })`, so nobody resamples anything.
SAMPLE_RATE = 24000

_BYTES_PER_SAMPLE = 2


class ClientChannel(Protocol):
    """The browser side of the session, narrowed to what the runtime uses."""

    async def send_json(self, data: dict) -> None: ...

    async def send_bytes(self, data: bytes) -> None: ...

    def __aiter__(self) -> AsyncIterator[bytes | dict]: ...


class VoiceSessionRuntime:
    def __init__(
        self,
        *,
        bridge: RealtimeBridge,
        client: ClientChannel,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
        max_session_sec: float,
    ) -> None:
        self._bridge = bridge
        self._client = client
        self._instructions = instructions
        self._voice = voice
        self._language = language
        self._params = params
        self._max_session_sec = max_session_sec

        # Audio actually forwarded to the browser, in ms. On a barge-in the
        # provider needs to know how much of its answer was really heard.
        self._played_ms = 0
        # Interrupting when the agent is silent makes the provider answer with
        # "no active response found" — a real error event for a non-event.
        self._agent_speaking = False
        self._last_inbound_audio_at: float | None = None
        self._transcript: list[dict] = []
        self._closed_reason: str | None = None

    @property
    def transcript(self) -> list[dict]:
        """Lives only as long as the session — nothing is persisted in this step."""
        return self._transcript

    async def run(self) -> str:
        """Drive the session to completion and return the reason it ended."""
        await self._bridge.connect(
            instructions=self._instructions,
            voice=self._voice,
            language=self._language,
            params=self._params,
        )
        await self._client.send_json(
            {
                "type": "session.ready",
                "inputSampleRate": SAMPLE_RATE,
                "outputSampleRate": SAMPLE_RATE,
            }
        )

        from_client = asyncio.create_task(self._pump_client())
        from_bridge = asyncio.create_task(self._pump_bridge())
        try:
            done, pending = await asyncio.wait(
                {from_client, from_bridge},
                timeout=self._max_session_sec,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                self._closed_reason = "timeout"
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            for task in done:
                task.result()
        finally:
            await self._bridge.close()

        reason = self._closed_reason or "completed"
        await self._client.send_json({"type": "session.closed", "reason": reason})
        return reason

    async def _pump_client(self) -> None:
        async for frame in self._client:
            if isinstance(frame, bytes):
                self._last_inbound_audio_at = time.monotonic()
                await self._bridge.send_audio(frame)
            elif frame.get("type") == "session.stop":
                self._closed_reason = "user_hangup"
                return

    async def _pump_bridge(self) -> None:
        async for event in self._bridge.events():
            match event:
                case AudioDelta():
                    self._agent_speaking = True
                    self._played_ms += len(event.pcm) // (_BYTES_PER_SAMPLE * SAMPLE_RATE // 1000)
                    await self._client.send_bytes(event.pcm)
                    await self._emit_timings()
                case UserTranscript():
                    await self._on_transcript("user", event.text, event.is_final)
                case AgentTranscript():
                    await self._on_transcript("assistant", event.text, event.is_final)
                case SpeechStarted():
                    # Two-sided barge-in: the browser drops what it has queued and
                    # the provider truncates to what was actually heard. Only a
                    # speaking agent can be interrupted.
                    await self._client.send_json({"type": "speech.started"})
                    if self._agent_speaking:
                        await self._bridge.interrupt(audio_end_ms=self._played_ms)
                        self._agent_speaking = False
                    self._played_ms = 0
                case TurnEnded():
                    self._agent_speaking = False
                    self._played_ms = 0
                case BridgeError():
                    await self._client.send_json(
                        {
                            "type": "error",
                            "code": event.code,
                            "message": event.message,
                            "isFatal": event.is_fatal,
                        }
                    )
                    if event.is_fatal:
                        self._closed_reason = "error"
                        return
                case SessionClosed():
                    self._closed_reason = event.reason
                    return

    async def _emit_timings(self) -> None:
        """One honest end-to-end number: last inbound audio → first audio back."""
        if self._last_inbound_audio_at is None:
            return
        first_audio_ms = int((time.monotonic() - self._last_inbound_audio_at) * 1000)
        self._last_inbound_audio_at = None
        await self._client.send_json({"type": "turn.timings", "firstAudioMs": first_audio_ms})

    async def _on_transcript(self, role: str, text: str, is_final: bool) -> None:
        if is_final:
            self._transcript.append({"role": role, "text": text})
        await self._client.send_json(
            {"type": "transcript", "role": role, "text": text, "isFinal": is_final}
        )
