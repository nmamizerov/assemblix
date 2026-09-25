"""LiveKitChannel: mic from the room, control from the WS, audio to the avatar."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from assemblix_api.realtime.livekit.channel import LiveKitChannel


class _Control:
    def __init__(self, frames: list[Any], hold: bool = False) -> None:
        self._frames = frames
        self._hold = hold
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def __aiter__(self) -> AsyncIterator[Any]:
        for frame in self._frames:
            yield frame
        if self._hold:
            await asyncio.sleep(3600)


class _Output:
    def __init__(self) -> None:
        self.pushed: list[tuple[bytes, int]] = []
        self.ended = 0

    async def push(self, pcm: bytes, sample_rate: int) -> None:
        self.pushed.append((pcm, sample_rate))

    async def end_utterance(self) -> None:
        self.ended += 1

    async def interrupt(self) -> int | None:
        return 321


async def _mic(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def test_merges_mic_audio_and_control_frames() -> None:
    # The WS stays open; the mic ending (user left) is what ends the stream.
    control = _Control([{"type": "session.stop"}], hold=True)
    channel = LiveKitChannel(control)
    channel.attach(mic=_mic([b"a", b"b"]), output=_Output(), output_sample_rate=24000)

    received = await asyncio.wait_for(_collect(channel), timeout=1)

    assert b"a" in received and b"b" in received
    assert {"type": "session.stop"} in received


async def test_ends_when_the_user_leaves_the_room() -> None:
    control = _Control([], hold=True)
    channel = LiveKitChannel(control)
    channel.attach(mic=_mic([b"a"]), output=_Output(), output_sample_rate=24000)

    received = await asyncio.wait_for(_collect(channel), timeout=1)

    assert received == [b"a"]


async def _collect(channel: LiveKitChannel) -> list[Any]:
    return [frame async for frame in channel]


class _RaisingControl:
    """Yields one frame, then blows up mid-iteration (e.g. a malformed WS frame)."""

    async def send_json(self, data: dict) -> None:
        raise AssertionError("not exercised")

    async def __aiter__(self) -> AsyncIterator[Any]:
        yield {"type": "ok"}
        raise ValueError("malformed control frame")


async def test_a_broken_control_socket_still_cancels_the_mic_drain() -> None:
    closed = asyncio.Event()

    async def mic() -> AsyncIterator[bytes]:
        try:
            while True:
                await asyncio.sleep(3600)
                yield b"never"
        finally:
            closed.set()

    channel = LiveKitChannel(_RaisingControl())
    channel.attach(mic=mic(), output=_Output(), output_sample_rate=24000)

    with pytest.raises(ValueError, match="malformed control frame"):
        await asyncio.wait_for(_collect(channel), timeout=1)

    assert closed.is_set()


async def test_outbound_goes_to_the_avatar_and_json_to_the_ws() -> None:
    control = _Control([])
    output = _Output()
    channel = LiveKitChannel(control)
    channel.attach(mic=_mic([]), output=output, output_sample_rate=16000)

    await channel.send_bytes(b"pcm")
    await channel.send_json({"type": "transcript"})
    await channel.end_of_utterance()

    assert channel.media == "livekit"
    assert output.pushed == [(b"pcm", 16000)]
    assert output.ended == 1
    assert control.sent == [{"type": "transcript"}]
    assert await channel.interrupt_playback() == 321


async def test_json_before_attach_still_reaches_the_ws() -> None:
    control = _Control([])
    channel = LiveKitChannel(control)

    await channel.send_json({"type": "session.ready"})
    await channel.end_of_utterance()  # no avatar yet: nothing to end
    assert await channel.interrupt_playback() is None

    assert control.sent == [{"type": "session.ready"}]
