"""Direct Yandex SpeechKit client for text-to-speech and speech-to-text.

SpeechKit is not OpenAI-compatible (its own REST API, per-request ``Api-Key`` auth
and a mandatory ``folderId``), so it is called directly rather than through litellm
— the same reason ElevenLabs has its own client module.

Yandex needs *two* secrets: an API key and a folder id. To keep the single-value
credential model intact, both are stored in one credential as ``"<folderId>:<apiKey>"``
and split here. The folder id is a fixed-format Yandex Cloud id with no colon and
comes first, so ``partition(":")`` is unambiguous even if the key contains a colon.

Unlike ElevenLabs, SpeechKit exposes a fixed catalog of voices (not listable per
key), so ``list_voices()`` returns a static list.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    import av

from assemblix_api.core.settings import get_settings

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# SpeechKit synthesis defaults. mp3 keeps the buffered-audio path uniform with
# ElevenLabs (the agent node emits format "mp3").
_TTS_LANG = "ru-RU"
_TTS_FORMAT = "mp3"

# SpeechKit's synchronous recognizer accepts only Ogg/Opus or raw LPCM — not the
# WebM container most browsers record. We therefore decode whatever came in to
# 16 kHz mono s16le PCM and send it as LPCM, which sidesteps container issues.
_STT_LANG = "ru-RU"
_STT_SAMPLE_RATE = 16000
# Sync recognition caps the body at 1 MB (~30 s of 16 kHz mono PCM).
_STT_MAX_LPCM_BYTES = 1024 * 1024


class YandexVoice(BaseModel):
    """One SpeechKit voice from the fixed catalog."""

    id: str
    name: str
    preview_url: str | None = None


# SpeechKit v1 premium voices (id == the API ``voice`` value). Static because
# SpeechKit has no per-key voice-listing endpoint.
_VOICES: tuple[YandexVoice, ...] = (
    YandexVoice(id="alena", name="Alena (ru, f)"),
    YandexVoice(id="filipp", name="Filipp (ru, m)"),
    YandexVoice(id="ermil", name="Ermil (ru, m)"),
    YandexVoice(id="jane", name="Jane (ru, f)"),
    YandexVoice(id="omazh", name="Omazh (ru, f)"),
    YandexVoice(id="zahar", name="Zahar (ru, m)"),
    YandexVoice(id="dasha", name="Dasha (ru, f)"),
    YandexVoice(id="julia", name="Julia (ru, f)"),
    YandexVoice(id="lera", name="Lera (ru, f)"),
    YandexVoice(id="masha", name="Masha (ru, f)"),
    YandexVoice(id="marina", name="Marina (ru, f)"),
    YandexVoice(id="alexander", name="Alexander (ru, m)"),
    YandexVoice(id="kirill", name="Kirill (ru, m)"),
    YandexVoice(id="anton", name="Anton (ru, m)"),
    YandexVoice(id="john", name="John (en, m)"),
)


def _tts_base_url() -> str:
    return get_settings().yandex_tts_api_base_url.rstrip("/")


def _stt_base_url() -> str:
    return get_settings().yandex_stt_api_base_url.rstrip("/")


def split_credential(value: str) -> tuple[str, str]:
    """Split a stored credential ``"<folderId>:<apiKey>"`` into ``(folder_id, api_key)``.

    Raises:
        ValueError: the credential is not in the expected ``folderId:apiKey`` form.
    """
    folder_id, sep, api_key = value.partition(":")
    if not sep or not folder_id or not api_key:
        raise ValueError("Yandex credential must be in the form '<folderId>:<apiKey>'")
    return folder_id, api_key


def list_voices() -> list[YandexVoice]:
    """Return the fixed SpeechKit voice catalog."""
    return list(_VOICES)


def _raise_for_yandex(resp: httpx.Response) -> None:
    """Raise with SpeechKit's error body attached (raise_for_status hides it)."""
    if resp.is_error:
        raise RuntimeError(f"Yandex SpeechKit {resp.status_code}: {resp.text}")


def _to_lpcm16k(audio_bytes: bytes) -> bytes:
    """Decode a recorded container (webm/ogg/mp4/…) to raw 16 kHz mono s16le PCM.

    Raises:
        ValueError: the audio cannot be decoded, or exceeds the sync ~30 s cap.
    """
    # Imported lazily so the transcoder never gates node/worker startup — only an
    # actual Yandex recognition call needs it.
    import av

    resampler = av.AudioResampler(format="s16", layout="mono", rate=_STT_SAMPLE_RATE)
    pcm = bytearray()

    def _emit(chunk: av.AudioFrame) -> None:
        # Packed mono s16 → one plane; slice off any alignment padding (avoids a
        # numpy dependency that frame.to_ndarray() would pull in).
        pcm.extend(bytes(chunk.planes[0])[: chunk.samples * 2])

    try:
        with av.open(io.BytesIO(audio_bytes)) as container:
            assert isinstance(container, av.container.InputContainer)
            stream = container.streams.audio[0]
            for frame in container.decode(stream):
                for chunk in resampler.resample(frame):
                    _emit(chunk)
            for chunk in resampler.resample(None):  # flush
                _emit(chunk)
    except (av.FFmpegError, IndexError) as exc:
        raise ValueError(f"Could not decode audio for Yandex recognition: {exc}") from exc
    if len(pcm) > _STT_MAX_LPCM_BYTES:
        raise ValueError("Audio is too long for Yandex synchronous recognition (max ~30 s)")
    return bytes(pcm)


async def synthesize(*, credential: str, voice: str, text: str) -> bytes:
    """Synthesize ``text`` with SpeechKit voice ``voice`` and return MP3 bytes."""
    folder_id, api_key = split_credential(credential)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_tts_base_url()}/tts:synthesize",
            headers={"Authorization": f"Api-Key {api_key}"},
            data={
                "text": text,
                "voice": voice,
                "folderId": folder_id,
                "lang": _TTS_LANG,
                "format": _TTS_FORMAT,
            },
        )
        _raise_for_yandex(resp)
        return resp.content


async def transcribe(*, credential: str, audio_bytes: bytes) -> str:
    """Recognize short audio (≤ ~30 s) via the synchronous STT endpoint.

    The inbound blob is transcoded to LPCM first, since SpeechKit does not accept
    the WebM container browsers record.
    """
    folder_id, api_key = split_credential(credential)
    pcm = _to_lpcm16k(audio_bytes)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_stt_base_url()}/stt:recognize",
            headers={"Authorization": f"Api-Key {api_key}"},
            params={
                "folderId": folder_id,
                "lang": _STT_LANG,
                "format": "lpcm",
                "sampleRateHertz": _STT_SAMPLE_RATE,
            },
            content=pcm,
        )
        _raise_for_yandex(resp)
        return resp.json().get("result", "")
