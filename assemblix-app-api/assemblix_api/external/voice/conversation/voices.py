"""Static voice catalogs for the speech-to-speech (conversation) providers.

Neither OpenAI nor Google exposes a programmatic voice-listing endpoint for their
realtime models — their voices are documented constants, not something you can
query per key. This mirrors ``external/voice/yandex.py``'s ``_VOICES`` catalog:
one static tuple per provider, served without any API call.
"""

from __future__ import annotations

from pydantic import BaseModel


class ConversationVoice(BaseModel):
    """One voice from a speech-to-speech provider's fixed catalog."""

    id: str
    name: str
    preview_url: str | None = None


# OpenAI realtime models (gpt-realtime-*) support a narrower voice set than the
# TTS catalog: "ash", "ballad", "coral", "fable", "onyx" and "nova" are TTS-only
# and fail at call time on a realtime session, so they are deliberately excluded
# here. "marin" and "cedar" are realtime-exclusive.
_OPENAI_VOICES: tuple[ConversationVoice, ...] = (
    ConversationVoice(id="alloy", name="Alloy"),
    ConversationVoice(id="echo", name="Echo"),
    ConversationVoice(id="sage", name="Sage"),
    ConversationVoice(id="shimmer", name="Shimmer"),
    ConversationVoice(id="verse", name="Verse"),
    ConversationVoice(id="marin", name="Marin"),
    ConversationVoice(id="cedar", name="Cedar"),
)

# Gemini Live voices. Ids are case-sensitive as required by the API.
_GEMINI_VOICES: tuple[ConversationVoice, ...] = (
    ConversationVoice(id="Puck", name="Puck"),
    ConversationVoice(id="Charon", name="Charon"),
    ConversationVoice(id="Kore", name="Kore"),
    ConversationVoice(id="Fenrir", name="Fenrir"),
    ConversationVoice(id="Aoede", name="Aoede"),
    ConversationVoice(id="Leda", name="Leda"),
    ConversationVoice(id="Orus", name="Orus"),
    ConversationVoice(id="Zephyr", name="Zephyr"),
)

_CATALOGS: dict[str, tuple[ConversationVoice, ...]] = {
    "openai": _OPENAI_VOICES,
    "gemini": _GEMINI_VOICES,
}


def list_conversation_voices(provider: str) -> list[ConversationVoice]:
    """Return the fixed conversation-voice catalog for ``provider`` (empty if none)."""
    return list(_CATALOGS.get(provider, ()))
