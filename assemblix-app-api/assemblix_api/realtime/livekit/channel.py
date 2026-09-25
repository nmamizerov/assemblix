"""The runtime's client channel for an avatar call.

Control frames still ride the WebSocket; the caller's microphone comes from the
LiveKit room and the agent's voice goes to the avatar participant. The channel
exists before the room is ready (the avatar joins while the provider connects),
so the media side is attached later.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

_DONE = object()


class LiveKitChannel:
    media = "livekit"

    def __init__(self, control: Any) -> None:
        self._control = control
        self._mic: AsyncIterator[bytes] | None = None
        self._output: Any = None
        self._output_rate = 0

    def attach(self, *, mic: AsyncIterator[bytes], output: Any, output_sample_rate: int) -> None:
        self._mic = mic
        self._output = output
        self._output_rate = output_sample_rate

    async def send_json(self, data: dict) -> None:
        await self._control.send_json(data)

    async def send_bytes(self, data: bytes) -> None:
        if self._output is not None:
            await self._output.push(data, self._output_rate)

    async def interrupt_playback(self) -> int | None:
        if self._output is None:
            return None
        return await self._output.interrupt()

    async def end_of_utterance(self) -> None:
        if self._output is not None:
            await self._output.end_utterance()

    async def __aiter__(self) -> AsyncIterator[bytes | dict]:
        assert self._mic is not None, "attach() must run before the runtime pumps"
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def drain(source: AsyncIterator[Any]) -> None:
            try:
                async for item in source:
                    await queue.put(item)
            finally:
                await queue.put(_DONE)

        # Either side ending ends the call: a closed WS is a hang-up, and so is a
        # caller whose microphone left the room.
        tasks = [
            asyncio.create_task(drain(self._control.__aiter__())),
            asyncio.create_task(drain(self._mic)),
        ]
        try:
            while (item := await queue.get()) is not _DONE:
                yield item
        finally:
            for task in tasks:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
