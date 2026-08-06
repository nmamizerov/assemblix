"""Conversation (speech-to-speech) provider seam — sibling of ``realtime_dispatch.py``.

One provider ships today. The factory exists so the runtime depends on the
``RealtimeBridge`` protocol rather than on a concrete adapter; adding Gemini is a
branch here plus one new module.
"""

from __future__ import annotations

from assemblix_api.external.voice.bridge import RealtimeBridge
from assemblix_api.external.voice.openai_bridge import OpenAIRealtimeBridge


def create_bridge(*, provider: str, api_key: str, model: str) -> RealtimeBridge:
    """Build the conversation bridge for ``provider``.

    Raises:
        NotImplementedError: the provider has no conversation route.
    """
    if provider == "openai":
        return OpenAIRealtimeBridge(api_key=api_key, model=model)
    raise NotImplementedError(f"No conversation route for provider {provider!r}")
