"""Direct ElevenLabs client for voice listing and text-to-speech.

ElevenLabs is not OpenAI-compatible (it has its own API and a voice catalog), so
it is called directly rather than through litellm — this is also what lets the UI
list a user's own voices.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

_BASE_URL = "https://api.elevenlabs.io/v1"
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class ElevenLabsVoice(BaseModel):
    """One voice from the account's voice library."""

    id: str
    name: str
    preview_url: str | None = None


async def list_voices(api_key: str) -> list[ElevenLabsVoice]:
    """Return the voices available to ``api_key`` (GET /v1/voices)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_BASE_URL}/voices", headers={"xi-api-key": api_key})
        resp.raise_for_status()
        data = resp.json()
    return [
        ElevenLabsVoice(id=v["voice_id"], name=v["name"], preview_url=v.get("preview_url"))
        for v in data.get("voices", [])
    ]


async def synthesize(*, api_key: str, voice_id: str, model: str, text: str) -> bytes:
    """Synthesize ``text`` with ``voice_id`` and return MP3 bytes."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_BASE_URL}/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": model},
        )
        resp.raise_for_status()
        return resp.content
