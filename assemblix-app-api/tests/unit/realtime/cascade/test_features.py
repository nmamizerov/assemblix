import numpy as np

from assemblix_api.realtime.cascade.features import log_mel


def test_log_mel_shape_and_range_for_eight_seconds() -> None:
    rng = np.random.default_rng(0)
    audio = rng.standard_normal(128_000).astype(np.float32) * 0.1

    features = log_mel(audio)

    assert features.shape == (80, 800)
    assert features.dtype == np.float32
    # Whisper scaling: (log10 + 4) / 4 with an 8-decade floor.
    assert features.max() - features.min() <= 2.0 + 1e-5


def test_log_mel_of_silence_is_flat() -> None:
    features = log_mel(np.zeros(128_000, dtype=np.float32))

    assert np.allclose(features, features[0, 0])
