"""ElevenLabs realtime text-to-speech over the stream-input WebSocket.

Feeds text incrementally (as an agent generates) and forwards PCM audio chunks + alignment
to ``on_audio`` from a concurrent receive loop. Live/best-effort: a WS error stops audio but
never raises out of ``send_text`` — the caller's text stream is unaffected. The stream ends on
the server's ``isFinal`` message (spike-confirmed).
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable

import structlog

from assemblix_api.core.settings import get_settings
from assemblix_api.schemas.debug_events import AlignmentData

logger = structlog.get_logger(__name__)

OnAudio = Callable[[bytes, AlignmentData | None], Awaitable[None]]


def _parse_alignment(raw: dict | None) -> AlignmentData | None:
    if not raw:
        return None
    # Accept both snake_case and ElevenLabs camelCase (spike: EL sends camelCase).
    return AlignmentData(
        chars=raw.get("chars", []),
        char_start_times_ms=raw.get("char_start_times_ms") or raw.get("charStartTimesMs", []),
        char_durations_ms=raw.get("char_durations_ms") or raw.get("charDurationsMs", []),
    )


class RealtimeTTSSession:
    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str,
        model: str,
        on_audio: OnAudio,
        connect: Callable[..., Awaitable] | None = None,
        output_format: str | None = None,
        chunk_schedule: list[int] | None = None,
    ):
        settings = get_settings()
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model
        self._on_audio = on_audio
        self._connect = connect
        self._output_format = output_format or settings.voice_realtime_output_format
        self._chunk_schedule = chunk_schedule or settings.voice_realtime_chunk_schedule
        self._ws_base = settings.elevenlabs_ws_base_url.rstrip("/")
        self._ws: object | None = None
        self._recv_task: asyncio.Task | None = None
        self._chars_sent = 0
        self._failed = False

    async def _default_connect(self, url: str) -> object:
        import websockets

        return await websockets.connect(url)

    async def open(self) -> None:
        url = (
            f"{self._ws_base}/text-to-speech/{self._voice_id}/stream-input"
            f"?model_id={self._model}&output_format={self._output_format}"
        )
        connect = self._connect or self._default_connect
        self._ws = await connect(url)
        # BOS: a single space primes the stream; carries voice_settings + xi_api_key.
        await self._ws.send(  # type: ignore[attr-defined]
            json.dumps(
                {
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                    "generation_config": {"chunk_length_schedule": self._chunk_schedule},
                    "xi_api_key": self._api_key,
                }
            )
        )
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            while True:
                message = await self._ws.recv()  # type: ignore[attr-defined]
                payload = json.loads(message)
                audio_b64 = payload.get("audio")
                if audio_b64:
                    pcm = base64.b64decode(audio_b64)
                    alignment = _parse_alignment(payload.get("normalizedAlignment"))
                    await self._on_audio(pcm, alignment)
                if payload.get("isFinal"):
                    break
        except Exception as exc:  # noqa: BLE001 — audio is best-effort; log and stop.
            self._failed = True
            logger.info("voice.realtime.recv_stopped", error=str(exc))

    async def send_text(self, text: str) -> None:
        if self._failed or self._ws is None:
            return
        try:
            await self._ws.send(  # type: ignore[attr-defined]
                json.dumps({"text": text, "try_trigger_generation": True})
            )
            self._chars_sent += len(text)
        except Exception as exc:  # noqa: BLE001 — best-effort.
            self._failed = True
            logger.info("voice.realtime.send_stopped", error=str(exc))

    async def flush_and_close(self) -> int:
        if self._ws is not None and not self._failed:
            try:
                await self._ws.send(json.dumps({"text": ""}))  # type: ignore[attr-defined]  # EOS
            except Exception:  # noqa: BLE001
                self._failed = True
        if self._recv_task is not None:
            try:
                await asyncio.wait_for(self._recv_task, timeout=30.0)
            except Exception:  # noqa: BLE001
                self._recv_task.cancel()
        await self.aclose()
        return self._chars_sent

    async def aclose(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
            self._ws = None

    async def __aenter__(self) -> "RealtimeTTSSession":
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.flush_and_close()
