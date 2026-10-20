from pathlib import Path
from typing import Any

import numpy as np
import pytest

from assemblix_api.realtime.cascade.models import SileroVad, SmartTurn


class _Input:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeVadSession:
    def __init__(self) -> None:
        self.feeds: list[dict[str, Any]] = []

    def run(self, _outputs: Any, feed: dict[str, Any]) -> list[Any]:
        self.feeds.append(feed)
        return [np.array([[0.9]], dtype=np.float32), feed["state"] + 1]


class _FakeTurnSession:
    def __init__(self) -> None:
        self.feeds: list[dict[str, Any]] = []

    def get_inputs(self) -> list[_Input]:
        return [_Input("input_features")]

    def run(self, _outputs: Any, feed: dict[str, Any]) -> list[Any]:
        self.feeds.append(feed)
        return [np.array([[0.73]], dtype=np.float32)]


def test_silero_prepends_context_and_carries_state() -> None:
    session = _FakeVadSession()
    vad = SileroVad(session)

    first = vad.speech_probability(np.ones(512, dtype=np.float32))
    vad.speech_probability(np.ones(512, dtype=np.float32))

    assert first == pytest.approx(0.9)
    assert session.feeds[0]["input"].shape == (1, 576)
    assert np.all(session.feeds[0]["input"][0, :64] == 0)
    # The second frame's context is the tail of the first frame.
    assert np.all(session.feeds[1]["input"][0, :64] == 1)
    assert np.all(session.feeds[1]["state"] == 1)
    assert session.feeds[0]["sr"] == 16000


def test_smart_turn_pads_short_audio_and_keeps_last_eight_seconds() -> None:
    session = _FakeTurnSession()
    model = SmartTurn(session)

    short = model.completion_probability(np.ones(16_000, dtype=np.float32))
    model.completion_probability(np.ones(200_000, dtype=np.float32))

    assert short == pytest.approx(0.73)
    assert session.feeds[0]["input_features"].shape == (1, 80, 800)
    assert session.feeds[1]["input_features"].shape == (1, 80, 800)


def test_loader_reports_missing_weights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from assemblix_api.core.settings import get_settings
    from assemblix_api.realtime.cascade import models

    monkeypatch.setattr(get_settings(), "turn_models_dir", str(tmp_path))
    models.load_turn_models.cache_clear()

    with pytest.raises(FileNotFoundError, match="make turn-models"):
        models.load_turn_models()
    models.load_turn_models.cache_clear()


@pytest.mark.external
def test_real_models_hear_silence_as_silence() -> None:
    from assemblix_api.realtime.cascade import models

    loaded = models.load_turn_models()
    vad = loaded.new_vad()

    probability = vad.speech_probability(np.zeros(512, dtype=np.float32))

    assert probability < 0.1
