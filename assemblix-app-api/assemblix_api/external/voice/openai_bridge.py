"""OpenAI realtime API adapter over the ``RealtimeBridge`` protocol.

Sibling of ``realtime.py`` (ElevenLabs streaming TTS): an injectable connection
factory for tests, a translation layer from provider event vocabulary to the
bridge's normalized events, and a best-effort posture where a transport failure
on an outbound send is logged and swallowed rather than raised into the
runtime's audio path. ``openai`` must not be imported anywhere else in this
package — it is the provider boundary.
"""

from __future__ import annotations

import base64
import inspect
from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog

from assemblix_api.external.voice.bridge import (
    AgentTranscript,
    AudioDelta,
    BridgeError,
    BridgeEvent,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)

logger = structlog.get_logger(__name__)

_AUDIO_FORMAT = {"type": "audio/pcm", "rate": 24000}
# params keys accepted for turn_detection; anything else is ignored, not forwarded.
_TURN_DETECTION_PARAMS = ("threshold", "prefix_padding_ms", "silence_duration_ms")


class OpenAIRealtimeBridge:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        connect_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._connect_factory = connect_factory
        self._connection: Any = None
        self._failed = False
        # id of the assistant item currently producing audio, for interrupt()'s truncate.
        self._active_item_id: str | None = None

    async def _default_connect(self, *, api_key: str, model: str) -> Any:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        manager = client.realtime.connect(model=model)
        return await manager.__aenter__()

    async def connect(
        self,
        *,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
    ) -> None:
        factory = self._connect_factory or self._default_connect
        result = factory(api_key=self._api_key, model=self._model)
        self._connection = await result if inspect.isawaitable(result) else result

        turn_detection: dict[str, Any] = {"type": "server_vad"}
        for key in _TURN_DETECTION_PARAMS:
            if key in params:
                turn_detection[key] = params[key]

        session: dict[str, Any] = {
            "type": "realtime",
            "instructions": instructions,
            "audio": {
                "input": {
                    "format": _AUDIO_FORMAT,
                    "transcription": {"language": language},
                    "turn_detection": turn_detection,
                },
                "output": {
                    "format": _AUDIO_FORMAT,
                    "voice": voice,
                },
            },
        }
        await self._connection.session.update(session=session)

    async def send_audio(self, pcm: bytes) -> None:
        if self._connection is None or self._failed:
            return
        try:
            await self._connection.input_audio_buffer.append(audio=base64.b64encode(pcm).decode())
        except Exception as exc:  # noqa: BLE001 — audio is best-effort; log and stop.
            self._failed = True
            logger.info("voice.openai_bridge.send_stopped", error=str(exc))

    async def interrupt(self, *, audio_end_ms: int) -> None:
        if self._connection is None or self._failed:
            return
        try:
            await self._connection.response.cancel()
            # output_audio_buffer.clear() is WebRTC/SIP only; over our plain WebSocket
            # transport, conversation.item.truncate is what actually stops in-flight
            # audio. Only meaningful while a turn is in flight — nothing to truncate
            # otherwise.
            if self._active_item_id is not None:
                await self._connection.conversation.item.truncate(
                    item_id=self._active_item_id,
                    content_index=0,
                    audio_end_ms=audio_end_ms,
                )
                self._active_item_id = None
        except Exception as exc:  # noqa: BLE001 — best-effort.
            self._failed = True
            logger.info("voice.openai_bridge.interrupt_stopped", error=str(exc))

    async def events(self) -> AsyncIterator[BridgeEvent]:
        assert self._connection is not None
        from openai import WebSocketConnectionClosedError
        from websockets.exceptions import ConnectionClosedError

        reason = "closed"
        try:
            async for event in self._connection:
                mapped = self._map_event(event)
                if mapped is not None:
                    yield mapped
        except (ConnectionClosedError, WebSocketConnectionClosedError) as exc:
            reason = str(exc)
        yield SessionClosed(reason=reason)

    def _map_event(self, event: Any) -> BridgeEvent | None:
        match event.type:
            case "input_audio_buffer.speech_started":
                return SpeechStarted()
            case "conversation.item.input_audio_transcription.delta":
                return UserTranscript(text=event.delta, is_final=False)
            case "conversation.item.input_audio_transcription.completed":
                return UserTranscript(text=event.transcript, is_final=True)
            case "response.output_item.added":
                # Track the assistant item currently producing audio so interrupt()
                # can target it with conversation.item.truncate.
                if getattr(event.item, "role", None) == "assistant":
                    self._active_item_id = event.item.id
                return None
            case "response.output_audio.delta":
                return AudioDelta(pcm=base64.b64decode(event.delta))
            case "response.output_audio_transcript.delta":
                return AgentTranscript(text=event.delta, is_final=False)
            case "response.output_audio_transcript.done":
                return AgentTranscript(text=event.transcript, is_final=True)
            case "response.done":
                self._active_item_id = None
                usage = event.response.usage
                return TurnEnded(
                    input_tokens=usage.input_tokens if usage else None,
                    output_tokens=usage.output_tokens if usage else None,
                )
            case "error":
                # server_error means the session/transport is broken; invalid_request_error
                # means a single bad client event was rejected and the session continues.
                return BridgeError(
                    code=event.error.code,
                    message=event.error.message,
                    is_fatal=event.error.type == "server_error",
                )
            case _:
                # Unknown/future event types are ignored, not fatal.
                return None

    async def close(self) -> None:
        if self._connection is None:
            return
        connection, self._connection = self._connection, None
        try:
            await connection.close()
        except Exception as exc:  # noqa: BLE001 — best-effort.
            logger.info("voice.openai_bridge.close_failed", error=str(exc))
