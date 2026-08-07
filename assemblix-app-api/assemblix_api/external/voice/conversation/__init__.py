"""Conversation (speech-to-speech) provider seam — sibling of ``realtime_dispatch.py``.

The factory exists so the runtime depends on the ``RealtimeBridge`` protocol rather
than on a concrete adapter. Adding a provider is a branch here plus one module that
translates its events; nothing provider-shaped may cross this boundary.
"""

from __future__ import annotations

from assemblix_api.external.voice.conversation.contract import RealtimeBridge
from assemblix_api.external.voice.conversation.gemini import GeminiLiveBridge
from assemblix_api.external.voice.conversation.openai import OpenAIRealtimeBridge


def create_bridge(*, provider: str, api_key: str, model: str) -> RealtimeBridge:
    """Build the conversation bridge for ``provider``.

    Raises:
        NotImplementedError: the provider has no conversation route.
    """
    if provider == "openai":
        return OpenAIRealtimeBridge(api_key=api_key, model=model)
    if provider == "gemini":
        return GeminiLiveBridge(api_key=api_key, model=model)
    raise NotImplementedError(f"No conversation route for provider {provider!r}")
