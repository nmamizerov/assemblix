"""ONNX models behind cascade turn-taking: Silero VAD and Smart Turn v3.

Sessions are loaded once per process and shared by every call; the only per-call
state is the VAD's recurrent state, held by the ``SileroVad`` handed to each call.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from assemblix_api.core.settings import get_settings
from assemblix_api.realtime.cascade.features import log_mel

SAMPLE_RATE = 16000
SILERO_FILE = "silero_vad.onnx"
SMART_TURN_FILE = "smart-turn-v3.onnx"


class VadModel(Protocol):
    frame_samples: int

    def speech_probability(self, frame: np.ndarray) -> float: ...


class SileroVad:
    frame_samples = 512
    _CONTEXT = 64

    def __init__(self, session: Any) -> None:
        self._session = session
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._CONTEXT), dtype=np.float32)
        self._sr = np.array(SAMPLE_RATE, dtype=np.int64)

    def speech_probability(self, frame: np.ndarray) -> float:
        x = np.concatenate([self._context, frame.reshape(1, -1).astype(np.float32)], axis=1)
        out, self._state = self._session.run(
            None, {"input": x, "state": self._state, "sr": self._sr}
        )
        self._context = x[:, -self._CONTEXT :]
        return float(np.asarray(out).reshape(-1)[0])


class SmartTurn:
    window_samples = 8 * SAMPLE_RATE

    def __init__(self, session: Any) -> None:
        self._session = session
        self._input = session.get_inputs()[0].name

    def completion_probability(self, audio: np.ndarray) -> float:
        clip = audio[-self.window_samples :].astype(np.float32)
        if len(clip) < self.window_samples:
            clip = np.pad(clip, (self.window_samples - len(clip), 0))
        clip = (clip - clip.mean()) / np.sqrt(clip.var() + 1e-7)
        out = self._session.run(None, {self._input: log_mel(clip)[np.newaxis]})
        return float(np.asarray(out[0]).reshape(-1)[0])


class TurnModels:
    def __init__(self, vad_session: Any, smart_turn: SmartTurn) -> None:
        self._vad_session = vad_session
        self.smart_turn = smart_turn

    def new_vad(self) -> SileroVad:
        return SileroVad(self._vad_session)


@functools.cache
def load_turn_models() -> TurnModels:
    import onnxruntime as ort

    directory = Path(get_settings().turn_models_dir)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1

    def session(name: str) -> Any:
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(f"Turn model missing: {path} — run `make turn-models`")
        return ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )

    return TurnModels(session(SILERO_FILE), SmartTurn(session(SMART_TURN_FILE)))
