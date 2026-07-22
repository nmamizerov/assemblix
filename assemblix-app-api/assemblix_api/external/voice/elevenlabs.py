"""Direct ElevenLabs client for voice listing and text-to-speech.

ElevenLabs is not OpenAI-compatible (it has its own API and a voice catalog), so
it is called directly rather than through litellm — this is also what lets the UI
list a user's own voices.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from assemblix_api.core.settings import get_settings

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _base_url() -> str:
    """ElevenLabs API base URL; override via ELEVENLABS_API_BASE_URL for a proxy."""
    return get_settings().elevenlabs_api_base_url.rstrip("/")


def _voices_url() -> str:
    """URL for the v2 voice-listing endpoint.

    Voice listing uses ``/v2/voices`` (paginated + server-side search); the
    configured base URL points at ``/v1`` (still used for TTS), so swap the
    trailing version segment.
    """
    base = _base_url()
    if base.endswith("/v1"):
        base = f"{base[:-3]}/v2"
    return f"{base}/voices"


def _client() -> httpx.AsyncClient:
    """Factory kept as a seam so tests can inject a MockTransport."""
    return httpx.AsyncClient(timeout=_TIMEOUT)


class ElevenLabsVoice(BaseModel):
    """One voice from the account's voice library."""

    id: str
    name: str
    preview_url: str | None = None


async def list_voices(api_key: str, *, search: str | None = None) -> list[ElevenLabsVoice]:
    """Return the voices available to ``api_key`` (GET /v2/voices).

    The legacy ``/v1/voices`` endpoint returns only a truncated default set; v2
    paginates the full library (max 100/page) and supports a server-side
    ``search`` over name/description/labels/category, which is forwarded here.
    All pages are drained so the caller gets every matching voice.
    """
    voices: list[ElevenLabsVoice] = []
    page_token: str | None = None
    async with _client() as client:
        while True:
            params: dict[str, str | int] = {"page_size": 100}
            if search:
                params["search"] = search
            if page_token:
                params["next_page_token"] = page_token
            resp = await client.get(_voices_url(), headers={"xi-api-key": api_key}, params=params)
            resp.raise_for_status()
            data = resp.json()
            voices.extend(
                ElevenLabsVoice(id=v["voice_id"], name=v["name"], preview_url=v.get("preview_url"))
                for v in data.get("voices", [])
            )
            page_token = data.get("next_page_token")
            if not data.get("has_more") or not page_token:
                break
    return voices


async def synthesize(*, api_key: str, voice_id: str, model: str, text: str) -> bytes:
    """Synthesize ``text`` with ``voice_id`` and return MP3 bytes."""
    async with _client() as client:
        resp = await client.post(
            f"{_base_url()}/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": model},
        )
        resp.raise_for_status()
        return resp.content
