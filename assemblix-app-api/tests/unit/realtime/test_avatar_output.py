"""The avatar protocol: one byte stream per utterance, RPCs for barge-in."""

from typing import Any

from assemblix_api.realtime.livekit.avatar_output import AvatarAudioOutput


class _Writer:
    def __init__(self) -> None:
        self.data = b""
        self.closed = False

    async def write(self, chunk: bytes) -> None:
        self.data += chunk

    async def aclose(self) -> None:
        self.closed = True


class _Participant:
    def __init__(self) -> None:
        self.streams: list[tuple[dict, _Writer]] = []
        self.rpcs: list[dict] = []
        self.handlers: dict[str, Any] = {}

    async def stream_bytes(self, name: str, **kwargs: Any) -> _Writer:
        writer = _Writer()
        self.streams.append((kwargs, writer))
        return writer

    async def perform_rpc(self, **kwargs: Any) -> str:
        self.rpcs.append(kwargs)
        return "ok"

    def register_rpc_method(self, name: str, handler: Any) -> None:
        self.handlers[name] = handler


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


_ONE_SECOND_24K = b"\x00\x00" * 24000


async def test_an_utterance_is_one_stream_closed_at_its_end() -> None:
    participant = _Participant()
    output = AvatarAudioOutput(participant, destination="avatar")

    await output.push(_ONE_SECOND_24K[:4800], 24000)
    await output.push(_ONE_SECOND_24K[:4800], 24000)
    await output.end_utterance()

    assert len(participant.streams) == 1
    kwargs, writer = participant.streams[0]
    assert kwargs["topic"] == "lk.audio_stream"
    assert kwargs["destination_identities"] == ["avatar"]
    assert kwargs["attributes"] == {"sample_rate": "24000", "num_channels": "1"}
    assert writer.data == _ONE_SECOND_24K[:4800] * 2
    assert writer.closed
    assert output.playing  # still audible until the avatar says it finished


async def test_playback_finished_rpc_clears_playing() -> None:
    participant = _Participant()
    output = AvatarAudioOutput(participant, destination="avatar")
    await output.push(_ONE_SECOND_24K, 24000)
    await output.end_utterance()

    participant.handlers["lk.playback_finished"](None)

    assert output.playing is False


async def test_a_late_playback_finished_does_not_silence_the_next_reply() -> None:
    participant = _Participant()
    output = AvatarAudioOutput(participant, destination="avatar")
    await output.push(_ONE_SECOND_24K, 24000)
    await output.end_utterance()
    await output.push(_ONE_SECOND_24K, 24000)  # next reply already streaming

    participant.handlers["lk.playback_finished"](None)  # about the previous one

    assert output.playing is True


async def test_interrupt_reports_what_was_heard_by_wall_clock() -> None:
    participant = _Participant()
    clock = _Clock()
    output = AvatarAudioOutput(participant, destination="avatar", clock=clock)
    await output.push(_ONE_SECOND_24K * 3, 24000)  # 3 s sent at once
    clock.now += 1.25  # the avatar has been talking for 1.25 s

    heard = await output.interrupt()

    assert heard == 1250
    assert participant.rpcs == [
        {"destination_identity": "avatar", "method": "lk.clear_buffer", "payload": ""}
    ]
    assert participant.streams[0][1].closed
    assert output.playing is False


async def test_heard_never_exceeds_what_was_sent() -> None:
    participant = _Participant()
    clock = _Clock()
    output = AvatarAudioOutput(participant, destination="avatar", clock=clock)
    await output.push(_ONE_SECOND_24K, 24000)
    clock.now += 5

    assert await output.interrupt() == 1000


async def test_interrupt_when_silent_is_none_and_sends_nothing() -> None:
    participant = _Participant()
    output = AvatarAudioOutput(participant, destination="avatar")

    assert await output.interrupt() is None
    assert participant.rpcs == []


async def test_a_16k_cascade_is_resampled_to_24k() -> None:
    participant = _Participant()
    output = AvatarAudioOutput(participant, destination="avatar")

    for _ in range(10):
        await output.push(b"\x00\x00" * 1600, 16000)  # 10 x 100 ms at 16 kHz
    await output.end_utterance()

    written = len(participant.streams[0][1].data)
    assert participant.streams[0][0]["attributes"]["sample_rate"] == "24000"
    assert abs(written - 48000) <= 2400  # ~1 s at 24 kHz, allowing resampler slack
