import asyncio

import numpy as np

from assemblix_api.realtime.cascade.turn import (
    EndOfTurn,
    PauseCancelled,
    PauseStart,
    SpeechStart,
    TurnDetector,
)
from assemblix_api.schemas.voice_agent import TurnConfig

FRAME = 512 * 2
SPEECH = b"\x10\x00" * 512
SILENCE = b"\x00\x00" * 512


class _ScriptedVad:
    """Speech iff the frame's first sample is non-zero."""

    frame_samples = 512

    def speech_probability(self, frame: np.ndarray) -> float:
        return 0.9 if frame[0] != 0 else 0.1


class _Completion:
    """Answers in order; the last answer repeats once the script runs out."""

    def __init__(self, answers: list[float]) -> None:
        self.answers = answers
        self.seen: list[int] = []
        self.audio: list[np.ndarray] = []

    async def __call__(self, audio: np.ndarray) -> float:
        self.seen.append(len(audio))
        self.audio.append(audio)
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def _detector(answers: list[float], **turn: object) -> tuple[TurnDetector, _Completion]:
    completion = _Completion(answers)
    return TurnDetector(
        vad=_ScriptedVad(), completion=completion, config=TurnConfig(**turn)
    ), completion


async def _feed(detector: TurnDetector, frames: list[bytes]) -> tuple[bytes, list[object]]:
    audio, signals = b"", []
    for frame in frames:
        update = await detector.push(frame)
        audio += update.stt_audio
        signals += update.signals
        while update.pending is not None:
            await asyncio.wait({update.pending})
            update = await detector.push(b"")
            audio += update.stt_audio
            signals += update.signals
    return audio, signals


async def test_complete_turn_ends_at_min_silence_with_preroll_forwarded() -> None:
    detector, completion = _detector([0.9])

    audio, signals = await _feed(detector, [SILENCE] * 3 + [SPEECH] * 10 + [SILENCE] * 7)

    assert signals == [
        SpeechStart(),
        PauseStart(),
        EndOfTurn(eou_ms=224, smart_turn_prob=0.9, smart_turn_asks=1),
    ]
    # 3 pre-roll + 10 speech + 7 pause frames reach STT; nothing before the pre-roll.
    assert len(audio) == FRAME * 20
    assert len(completion.seen) == 1


async def test_incomplete_turn_waits_for_max_silence() -> None:
    detector, _ = _detector([0.1], max_silence_ms=640)

    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE] * 19)
    assert signals == [SpeechStart(), PauseStart()]

    _, signals = await _feed(detector, [SILENCE])
    # Asked at 224, 384 and 544 ms of silence; the hard cap still ends the turn.
    assert signals == [EndOfTurn(eou_ms=640, smart_turn_prob=0.1, smart_turn_asks=3)]


async def test_resumed_speech_is_the_same_turn_and_asks_again() -> None:
    detector, completion = _detector([0.1, 0.9])

    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE] * 7 + [SPEECH] * 5 + [SILENCE] * 7)

    assert signals == [
        SpeechStart(),
        PauseStart(),
        PauseCancelled(),
        PauseStart(),
        EndOfTurn(eou_ms=224, smart_turn_prob=0.9, smart_turn_asks=2),
    ]
    assert len(completion.seen) == 2


async def test_single_click_is_not_speech() -> None:
    detector, completion = _detector([])

    audio, signals = await _feed(detector, [SPEECH, SILENCE, SPEECH, SILENCE] * 5)

    assert signals == []
    assert audio == b""
    assert completion.seen == []


async def test_smart_turn_sees_at_most_eight_seconds() -> None:
    detector, completion = _detector([0.9])

    await _feed(detector, [SPEECH] * 400 + [SILENCE] * 7)  # ~12.8 s of speech

    assert len(completion.seen) == 1 and 120_000 <= completion.seen[0] <= 8 * 16000


async def test_without_smart_turn_only_max_silence_ends_the_turn() -> None:
    detector, completion = _detector([], smart_turn=False, max_silence_ms=320)

    _, signals = await _feed(detector, [SPEECH] * 3 + [SILENCE] * 10)

    assert signals == [SpeechStart(), EndOfTurn(eou_ms=320)]
    assert completion.seen == []


async def test_partial_frames_are_buffered_across_pushes() -> None:
    detector, _ = _detector([0.9])

    # 300 + 724 + 1024 + 700 bytes: exactly two whole frames plus a 700-byte remainder.
    audio, signals = await _feed(detector, [SPEECH[:300], SPEECH[300:] + SPEECH + SPEECH[:700]])

    assert signals == [SpeechStart()]
    assert len(audio) == FRAME * 2


async def test_smart_turn_audio_ends_at_the_last_speech_frame() -> None:
    detector, completion = _detector([0.9])

    await _feed(detector, [SPEECH] * 10 + [SILENCE] * 7)

    audio = completion.audio[0]
    assert len(audio) == 10 * 512
    assert np.all(audio[-512:] != 0)


async def test_pause_start_is_signalled_before_smart_turn_answers() -> None:
    gate = asyncio.Event()

    async def completion(audio: np.ndarray) -> float:
        await gate.wait()
        return 0.9

    detector = TurnDetector(vad=_ScriptedVad(), completion=completion, config=TurnConfig())
    await _feed(detector, [SPEECH] * 5)

    update = await detector.push(SILENCE * 9)
    assert update.signals == [PauseStart()] and update.pending is not None
    assert len(update.stt_audio) == FRAME * 7  # the frames after the ask stay buffered
    # More audio while the ask is in flight is only buffered, never waited on.
    later = await detector.push(SILENCE)
    assert later.signals == [] and later.stt_audio == b"" and later.pending is update.pending

    gate.set()
    await update.pending
    update = await detector.push(b"")
    assert update.signals == [EndOfTurn(eou_ms=224, smart_turn_prob=0.9, smart_turn_asks=1)]
    assert len(update.stt_audio) == 0


async def test_resumed_speech_cancels_the_pause() -> None:
    detector, _ = _detector([0.1])

    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE] * 8 + [SPEECH] * 2)

    assert signals == [SpeechStart(), PauseStart(), PauseCancelled()]


async def test_decaying_threshold_ends_at_the_first_ask_that_clears_it() -> None:
    # Thresholds at 224/384/544 ms of silence: ~0.49, ~0.45, ~0.41.
    detector, completion = _detector([0.3, 0.44, 0.42])

    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE] * 30)

    assert signals == [
        SpeechStart(),
        PauseStart(),
        EndOfTurn(eou_ms=544, smart_turn_prob=0.42, smart_turn_asks=3),
    ]
    assert len(completion.seen) == 3


async def test_a_steady_probability_clears_the_threshold_once_it_has_decayed() -> None:
    detector, _ = _detector([0.4])

    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE] * 30)

    assert signals[-1] == EndOfTurn(eou_ms=704, smart_turn_prob=0.4, smart_turn_asks=4)


async def test_smart_turn_is_never_asked_twice_at_once() -> None:
    in_flight = 0
    peak = 0
    asks = 0

    async def completion(audio: np.ndarray) -> float:
        nonlocal in_flight, peak, asks
        in_flight += 1
        asks += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.001)
        in_flight -= 1
        return 0.0

    detector = TurnDetector(vad=_ScriptedVad(), completion=completion, config=TurnConfig())
    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE * 60])

    assert peak == 1
    assert signals[-1] == EndOfTurn(eou_ms=1504, smart_turn_prob=0.0, smart_turn_asks=asks)
    assert asks == 8  # every 160 ms (5 frames) from 224 ms until the 1500 ms cap


async def test_without_speculation_no_pause_signals_are_sent() -> None:
    detector, _ = _detector([0.1, 0.9], speculative=False)

    updates = []
    for frame in [SPEECH] * 5 + [SILENCE] * 7 + [SPEECH] * 5 + [SILENCE] * 7:
        update = await detector.push(frame)
        updates.append(update)
        if update.pending is not None:
            await update.pending
    updates.append(await detector.push(b""))

    assert [s for update in updates for s in update.signals] == [
        SpeechStart(),
        EndOfTurn(eou_ms=224, smart_turn_prob=0.9, smart_turn_asks=2),
    ]


async def test_reask_cadence_spreads_asks_up_to_a_long_max_silence() -> None:
    detector, completion = _detector([0.0], max_silence_ms=3200)

    await _feed(detector, [SPEECH] * 5 + [SILENCE] * 101)

    # (3200 - 200) / 10 = 300 ms apart: asks at 224, 544, ... 3104 ms.
    assert len(completion.seen) == 10


async def test_close_cancels_an_ask_in_flight() -> None:
    gate = asyncio.Event()

    async def completion(audio: np.ndarray) -> float:
        await gate.wait()
        return 0.9

    detector = TurnDetector(vad=_ScriptedVad(), completion=completion, config=TurnConfig())
    update = await detector.push(SPEECH * 5 + SILENCE * 7)
    assert update.pending is not None

    detector.close()
    await asyncio.sleep(0)

    assert update.pending.cancelled()
