"""Server-side text-to-speech seam — sibling of transcription.py.

``synthesize()`` turns text into audio bytes, hiding the provider behind the voice
registry. Only the ElevenLabs 'speech' route ships today; other providers slot in
by adding a registry entry + a branch here.
"""

from __future__ import annotations

from pydantic import BaseModel

from assemblix_api.external.voice import elevenlabs
from assemblix_api.external.voice.voice_catalog import find_voice_model


class SynthesisResult(BaseModel):
    """Result of a speech-synthesis call."""

    audio_bytes: bytes
    chars: int
    provider: str
    model: str


async def synthesize(
    *,
    text: str,
    provider: str,
    model: str,
    voice_id: str | None,
    api_key: str,
) -> SynthesisResult:
    """Synthesize ``text`` with ``(provider, model, voice_id)``.

    Raises:
        ValueError: the model is not a registered speech model, or no voice_id.
        NotImplementedError: the provider has no synthesis route yet.
    """
    meta = find_voice_model(provider, model)
    if meta is None or meta.capability != "speech":
        raise ValueError(f"Unknown or unsupported speech model: {provider}/{model}")

    if provider == "elevenlabs":
        if not voice_id:
            raise ValueError("A voice_id is required for ElevenLabs synthesis")
        audio = await elevenlabs.synthesize(
            api_key=api_key, voice_id=voice_id, model=model, text=text
        )
        return SynthesisResult(audio_bytes=audio, chars=len(text), provider=provider, model=model)

    raise NotImplementedError(f"No synthesis route for provider {provider!r}")
