"""Server-side speech-to-text over LiteLLM.

``transcribe()`` turns an inbound audio blob into text, hiding the provider
behind the same LiteLLM seam the chat models use. The model's registry entry
picks the route:

* ``transcription`` — the OpenAI-compatible transcription endpoint
  (``litellm.atranscription``): Whisper / gpt-4o-transcribe. Shipped.
* ``completion`` — audio as a multimodal part to a chat model (Gemini). Wired as
  the extension point but not enabled yet.
"""

from __future__ import annotations

import litellm
from pydantic import BaseModel

from assemblix_api.core.settings import get_settings
from assemblix_api.external.llm.provider_config import get_provider_config
from assemblix_api.external.voice.voice_catalog import find_voice_model


class Transcript(BaseModel):
    """Result of a transcription call."""

    text: str
    language: str | None = None
    duration: float | None = None


def _resolve_api_base(provider: str) -> str | None:
    """Reuse the chat provider transport config so voice honors the same proxy."""
    cfg = get_provider_config(provider)
    if not cfg.api_base_setting:
        return None
    return getattr(get_settings(), cfg.api_base_setting, None)


async def transcribe(
    *,
    audio_bytes: bytes,
    filename: str,
    provider: str,
    model: str,
    api_key: str,
) -> Transcript:
    """Transcribe ``audio_bytes`` to text using the given provider/model.

    Raises:
        ValueError: the ``(provider, model)`` pair is not in the voice registry.
        NotImplementedError: the model routes through ``completion`` (Gemini),
            which is not enabled yet.
    """
    meta = find_voice_model(provider, model)
    if meta is None:
        raise ValueError(f"Unknown or unsupported voice model: {provider}/{model}")

    if meta.route == "transcription":
        response = await litellm.atranscription(
            model=model,  # bare id, e.g. "whisper-1" (no provider prefix here)
            file=(filename, audio_bytes),
            api_key=api_key,
            api_base=_resolve_api_base(provider),
            response_format="verbose_json",
        )
        return Transcript(
            text=response.text,
            language=getattr(response, "language", None),
            duration=getattr(response, "duration", None),
        )

    # route == "completion" — Gemini audio via the chat endpoint. The seam lives
    # here; enabling it is a follow-up once verified on the pinned litellm.
    raise NotImplementedError(
        f"Voice model {provider}/{model} uses the 'completion' route, which is not enabled yet"
    )
