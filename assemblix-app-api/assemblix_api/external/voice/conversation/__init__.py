"""Conversation (speech-to-speech) provider seam — sibling of ``realtime_dispatch.py``.

The factory exists so the runtime depends on the ``RealtimeBridge`` protocol rather
than on a concrete adapter. Adding a provider is a branch here plus one module that
translates its events; nothing provider-shaped may cross this boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from assemblix_api.external.voice import speech_out as speech_out_module
from assemblix_api.external.voice.conversation.contract import RealtimeBridge
from assemblix_api.external.voice.conversation.gemini import GeminiLiveBridge
from assemblix_api.external.voice.conversation.half_cascade import HalfCascadeBridge
from assemblix_api.external.voice.conversation.openai import OpenAIRealtimeBridge
from assemblix_api.external.voice.speech_out import SpeechOutput

if TYPE_CHECKING:
    from assemblix_api.realtime.cascade.setup import CascadeMeter, CascadeSetup


def create_bridge(
    *,
    provider: str,
    api_key: str,
    model: str,
    api_base: str | None = None,
    speech_out: SpeechOutput | None = None,
    cascade: CascadeSetup | None = None,
    meter: CascadeMeter | None = None,
) -> RealtimeBridge:
    """Build the conversation bridge for ``provider``.

    ``api_base`` is the configured transport base URL — the same proxy the chat
    and transcription routes use. ``None`` means the provider SDK's own default.
    ``speech_out`` swaps the model's own voice for a streaming TTS provider: the
    model then answers in text and that text is spoken here.

    Raises:
        NotImplementedError: the provider has no conversation route.
    """
    inner: RealtimeBridge
    if provider == "cascade":
        if cascade is None or meter is None or speech_out is None:
            raise ValueError("A cascade bridge needs its setup, a meter and a speech output")
        from assemblix_api.realtime.cascade.bridge import build_cascade_bridge

        inner = build_cascade_bridge(cascade, meter)
    elif provider == "openai":
        inner = OpenAIRealtimeBridge(api_key=api_key, model=model, api_base=api_base)
    elif provider == "gemini":
        inner = GeminiLiveBridge(api_key=api_key, model=model, api_base=api_base)
    else:
        raise NotImplementedError(f"No conversation route for provider {provider!r}")
    if speech_out is None:
        return inner
    return HalfCascadeBridge(
        inner=inner,
        speech_out=speech_out,
        output_sample_rate=speech_out_module.output_sample_rate(speech_out),
    )
