"""LiveAvatar session socket: chunked speech, barge-in, keep-alive, vendor hang-up."""

import asyncio
import base64
import json
from typing import Any

import pytest

from assemblix_api.external.avatar.errors import AvatarUnavailable
from assemblix_api.external.avatar.liveavatar_socket import LiveAvatarSocketOutput

_MS_24K = 48  # bytes per millisecond of 24 kHz mono s16le


class _Socket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()
        self.closed = False

    async def send(self, data: str) -> None:
        self.sent.append(json.loads(data))

    def feed(self, **event: Any) -> None:
        self.incoming.put_nowait(json.dumps(event))

    def hang_up(self) -> None:
        self.incoming.put_nowait(None)

    def __aiter__(self) -> "_Socket":
        return self

    async def __anext__(self) -> str:
        item = await self.incoming.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self) -> None:
        self.closed = True


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


async def _connected(ws: _Socket, **kwargs: Any) -> LiveAvatarSocketOutput:
    output = LiveAvatarSocketOutput(ws, first_chunk_ms=200, **kwargs)
    ws.feed(type="session.state_updated", state="connected")
    await output.wait_connected()
    return output


def _audio_len(message: dict[str, Any]) -> int:
    return len(base64.b64decode(message.get("audio", "")))


def _types(ws: _Socket) -> list[str]:
    return [m["type"] for m in ws.sent]


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


async def test_waits_for_connected_before_sending() -> None:
    # Arrange
    ws = _Socket()
    output = LiveAvatarSocketOutput(ws, first_chunk_ms=200)
    waiter = asyncio.create_task(output.wait_connected())
    ws.feed(type="session.state_updated", state="new")
    await _settle()

    # Assert
    assert not waiter.done()
    ws.feed(type="session.state_updated", state="connected")
    await asyncio.wait_for(waiter, timeout=1)
    await output.aclose()


async def test_socket_closed_before_connected_is_unavailable() -> None:
    ws = _Socket()
    output = LiveAvatarSocketOutput(ws, first_chunk_ms=200)
    ws.hang_up()

    with pytest.raises(AvatarUnavailable):
        await asyncio.wait_for(output.wait_connected(), timeout=1)


async def test_first_chunk_flushes_at_first_chunk_ms() -> None:
    # Arrange
    ws = _Socket()
    output = await _connected(ws)

    # Act
    await output.push(b"\0" * 100 * _MS_24K, 24000)
    assert ws.sent == []
    await output.push(b"\0" * 100 * _MS_24K, 24000)

    # Assert
    assert _types(ws) == ["agent.speak"]
    assert _audio_len(ws.sent[0]) == 200 * _MS_24K
    assert ws.sent[0]["event_id"]
    await output.aclose()


async def test_then_sends_one_second_chunks() -> None:
    # Arrange
    ws = _Socket()
    output = await _connected(ws)
    await output.push(b"\0" * 200 * _MS_24K, 24000)

    # Act
    await output.push(b"\0" * 1000 * _MS_24K, 24000)

    # Assert
    assert _types(ws) == ["agent.speak", "agent.speak"]
    assert _audio_len(ws.sent[1]) == 1000 * _MS_24K
    await output.aclose()


async def test_end_utterance_sends_remainder_then_speak_end() -> None:
    # Arrange
    ws = _Socket()
    output = await _connected(ws)
    await output.push(b"\0" * 300 * _MS_24K, 24000)

    # Act
    await output.end_utterance()

    # Assert
    assert _types(ws) == ["agent.speak", "agent.speak", "agent.speak_end"]
    assert _audio_len(ws.sent[1]) == 100 * _MS_24K
    await output.aclose()


async def test_resamples_16khz_to_24khz() -> None:
    # Arrange
    ws = _Socket()
    output = await _connected(ws)

    # Act
    await output.push(b"\0" * 32000, 16000)
    await output.end_utterance()

    # Assert
    total = sum(_audio_len(m) for m in ws.sent)
    assert abs(total - 48000) <= 10 * _MS_24K
    await output.aclose()


async def test_interrupt_sends_interrupt_and_returns_heard_ms() -> None:
    # Arrange
    ws = _Socket()
    clock = _Clock()
    output = await _connected(ws, clock=clock)
    await output.push(b"\0" * 500 * _MS_24K, 24000)  # 200 ms sent, 300 ms buffered
    clock.now += 0.15

    # Act
    heard = await output.interrupt()

    # Assert
    assert heard == 150
    assert _types(ws)[-1] == "agent.interrupt"
    assert output.playing is False
    await output.aclose()


async def test_interrupt_with_only_buffered_audio_sends_nothing() -> None:
    # Arrange
    ws = _Socket()
    output = await _connected(ws)
    await output.push(b"\0" * 50 * _MS_24K, 24000)

    # Act
    heard = await output.interrupt()
    await output.push(b"\0" * 200 * _MS_24K, 24000)

    # Assert
    assert heard == 0
    assert _types(ws) == ["agent.speak"]
    assert _audio_len(ws.sent[0]) == 200 * _MS_24K
    await output.aclose()


async def test_interrupt_when_idle_returns_none() -> None:
    ws = _Socket()
    output = await _connected(ws)

    assert await output.interrupt() is None
    assert ws.sent == []
    await output.aclose()


async def test_speak_ended_for_the_last_utterance_clears_playing() -> None:
    # Arrange
    ws = _Socket()
    output = await _connected(ws)
    await output.push(b"\0" * 200 * _MS_24K, 24000)
    await output.end_utterance()
    utterance = ws.sent[0]["event_id"]

    # Act
    ws.feed(type="agent.speak_ended", source_event_id="older-utterance")
    await _settle()
    still_playing = output.playing
    ws.feed(type="agent.speak_ended", source_event_id=utterance)
    await _settle()

    # Assert
    assert still_playing is True
    assert output.playing is False
    await output.aclose()


async def test_keepalive_after_idle() -> None:
    ws = _Socket()
    output = await _connected(ws, keepalive_seconds=0.05)

    await asyncio.sleep(0.15)

    assert "session.keep_alive" in _types(ws)
    await output.aclose()


async def test_push_after_vendor_closed_raises_unavailable() -> None:
    # Arrange
    ws = _Socket()
    output = await _connected(ws)
    ws.hang_up()
    await _settle()

    # Act / Assert
    with pytest.raises(AvatarUnavailable):
        await output.push(b"\0" * 10 * _MS_24K, 24000)
    await output.aclose()


async def test_aclose_closes_the_socket() -> None:
    ws = _Socket()
    output = await _connected(ws)

    await output.aclose()

    assert ws.closed
