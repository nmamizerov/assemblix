"""Whisper-compatible log-mel features (80 bins, 10 ms hop) for Smart Turn v3."""

from __future__ import annotations

import numpy as np

_SAMPLE_RATE = 16000
_N_FFT = 400
_HOP = 160
_N_MELS = 80


def _hz_to_mel(freq: np.ndarray) -> np.ndarray:
    f_sp = 200.0 / 3
    min_log_hz = 1000.0
    min_log_mel = min_log_hz / f_sp
    logstep = np.log(6.4) / 27.0
    return np.where(
        freq >= min_log_hz,
        min_log_mel + np.log(np.maximum(freq, min_log_hz) / min_log_hz) / logstep,
        freq / f_sp,
    )


def _mel_to_hz(mels: np.ndarray) -> np.ndarray:
    f_sp = 200.0 / 3
    min_log_hz = 1000.0
    min_log_mel = min_log_hz / f_sp
    logstep = np.log(6.4) / 27.0
    return np.where(
        mels >= min_log_mel,
        min_log_hz * np.exp(logstep * (mels - min_log_mel)),
        f_sp * mels,
    )


def _mel_filters() -> np.ndarray:
    fft_freqs = np.linspace(0, _SAMPLE_RATE / 2, _N_FFT // 2 + 1)
    edges = _hz_to_mel(np.array([0.0, _SAMPLE_RATE / 2]))
    mel_points = _mel_to_hz(np.linspace(edges[0], edges[1], _N_MELS + 2))
    widths = np.diff(mel_points)
    ramps = mel_points[:, None] - fft_freqs[None, :]
    lower = -ramps[:-2] / widths[:-1, None]
    upper = ramps[2:] / widths[1:, None]
    weights = np.maximum(0.0, np.minimum(lower, upper))
    weights *= (2.0 / (mel_points[2:] - mel_points[:-2]))[:, None]
    return weights.astype(np.float32)


_FILTERS = _mel_filters()
_WINDOW = np.hanning(_N_FFT + 1)[:-1].astype(np.float32)


def log_mel(audio: np.ndarray) -> np.ndarray:
    padded = np.pad(audio.astype(np.float32), _N_FFT // 2, mode="reflect")
    n_frames = 1 + (len(padded) - _N_FFT) // _HOP
    index = np.arange(_N_FFT)[None, :] + _HOP * np.arange(n_frames)[:, None]
    spectrum = np.abs(np.fft.rfft(padded[index] * _WINDOW, n=_N_FFT, axis=1)) ** 2
    mel = (_FILTERS @ spectrum.T)[:, :-1]
    log = np.log10(np.maximum(mel, 1e-10))
    log = np.maximum(log, log.max() - 8.0)
    return ((log + 4.0) / 4.0).astype(np.float32)
