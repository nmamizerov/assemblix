import numpy as np

from assemblix_api.realtime.cascade.turn import EndOfTurn, SpeechStart, TurnDetector
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
    def __init__(self, answers: list[float]) -> None:
        self.answers = answers
        self.seen: list[int] = []
        self.audio: list[np.ndarray] = []

    async def __call__(self, audio: np.ndarray) -> float:
        self.seen.append(len(audio))
        self.audio.append(audio)
        return self.answers.pop(0)


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
    return audio, signals


async def test_complete_turn_ends_at_min_silence_with_preroll_forwarded() -> None:
    detector, completion = _detector([0.9])

    audio, signals = await _feed(detector, [SILENCE] * 3 + [SPEECH] * 10 + [SILENCE] * 7)

    assert signals == [SpeechStart(), EndOfTurn(eou_ms=224)]
    # 3 pre-roll + 10 speech + 7 pause frames reach STT; nothing before the pre-roll.
    assert len(audio) == FRAME * 20
    assert len(completion.seen) == 1


async def test_incomplete_turn_waits_for_max_silence() -> None:
    detector, _ = _detector([0.1], max_silence_ms=640)

    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE] * 19)
    assert signals == [SpeechStart()]

    _, signals = await _feed(detector, [SILENCE])
    assert signals == [EndOfTurn(eou_ms=640)]


async def test_resumed_speech_is_the_same_turn_and_asks_again() -> None:
    detector, completion = _detector([0.1, 0.9])

    _, signals = await _feed(detector, [SPEECH] * 5 + [SILENCE] * 7 + [SPEECH] * 5 + [SILENCE] * 7)

    assert signals == [SpeechStart(), EndOfTurn(eou_ms=224)]
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
