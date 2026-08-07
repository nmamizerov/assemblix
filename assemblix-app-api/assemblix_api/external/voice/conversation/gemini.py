"""Gemini Live adapter over the ``RealtimeBridge`` protocol.

Sibling of ``openai.py``, and the file that proves the seam is real: this provider
disagrees with OpenAI on three things, and all three stop here.

* **Sample rates.** It listens at 16kHz and answers at 24kHz, where OpenAI is 24kHz
  both ways. The rates are declared on the bridge and travel to the browser.
* **Interruption.** There is no client-side truncate — barge-in is entirely
  server-side (``START_OF_ACTIVITY_INTERRUPTS``), announced after the fact through
  ``server_content.interrupted``. ``interrupt()`` is therefore a no-op.
* **Transcription.** Text arrives as fragments, and the `finished` flag the SDK
  models is not actually delivered — so the adapter both accumulates the sentence and
  decides where it ends.

``google.genai`` must not be imported anywhere else in this package — it is the
provider boundary.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    BridgeEvent,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    UserTranscript,
)

logger = structlog.get_logger(__name__)

_INPUT_SAMPLE_RATE = 16000
_OUTPUT_SAMPLE_RATE = 24000
_INPUT_MIME_TYPE = f"audio/pcm;rate={_INPUT_SAMPLE_RATE}"

# Gemini wants BCP-47 for speech synthesis while the rest of the platform stores a
# plain ISO-639-1 code. Only the languages the agent form offers need an entry;
# anything else is passed through and left to the provider to accept or reject.
_BCP47: dict[str, str] = {
    "ru": "ru-RU",
    "en": "en-US",
    "es": "es-ES",
    "de": "de-DE",
    "fr": "fr-FR",
    "it": "it-IT",
    "pt": "pt-BR",
    "pl": "pl-PL",
    "tr": "tr-TR",
    "nl": "nl-NL",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh": "cmn-CN",
    "ar": "ar-XA",
    "hi": "hi-IN",
}

# params keys accepted for VAD tuning; anything else is ignored, not forwarded.
_ACTIVITY_DETECTION_PARAMS = ("prefix_padding_ms", "silence_duration_ms")


class GeminiLiveBridge:
    input_sample_rate = _INPUT_SAMPLE_RATE
    output_sample_rate = _OUTPUT_SAMPLE_RATE

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        connect_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._connect_factory = connect_factory
        self._session: Any = None
        # ``live.connect`` is an @asynccontextmanager. Dropping the manager lets the
        # garbage collector finalize its async generator, which runs the generator's
        # `finally` and closes the socket — the call would hang up on itself with a
        # clean 1000 the moment the reference went out of scope.
        self._manager: Any = None
        self._failed = False
        # Transcription arrives as deltas and never carries a completed form, so
        # the accumulated sentence is kept here until the adapter closes it off.
        self._user_text = ""
        self._agent_text = ""
        self._usage: tuple[int | None, int | None] = (None, None)

    async def _default_connect(self, *, api_key: str, model: str, config: Any) -> Any:
        from google import genai

        client = genai.Client(api_key=api_key)
        self._manager = client.aio.live.connect(model=model, config=config)
        return await self._manager.__aenter__()

    async def connect(
        self,
        *,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
    ) -> None:
        from google.genai import types

        activity_detection = types.AutomaticActivityDetection(
            **{key: params[key] for key in _ACTIVITY_DETECTION_PARAMS if key in params}
        )
        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=instructions,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                ),
                language_code=_BCP47.get(language, language),
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=activity_detection,
                activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
            ),
        )

        factory = self._connect_factory or self._default_connect
        result = factory(api_key=self._api_key, model=self._model, config=config)
        self._session = await result if inspect.isawaitable(result) else result

    async def send_audio(self, pcm: bytes) -> None:
        if self._session is None or self._failed:
            return
        from google.genai import types

        try:
            # `audio=`, not `media=`: the latter routes to the deprecated media_chunks
            # field and the server closes the socket with 1007 on the first frame.
            await self._session.send_realtime_input(
                audio=types.Blob(data=pcm, mime_type=_INPUT_MIME_TYPE)
            )
        except Exception as exc:  # noqa: BLE001 — audio is best-effort; log and stop.
            self._failed = True
            logger.info("voice.gemini_bridge.send_stopped", error=str(exc))

    async def interrupt(self, *, audio_end_ms: int) -> None:
        """No-op: this provider interrupts itself and reports it after the fact."""

    async def events(self) -> AsyncIterator[BridgeEvent]:
        assert self._session is not None

        reason = "closed"
        try:
            # receive() ends its iteration on every turn_complete, so a single
            # `async for` would hang up after the agent's first answer.
            while True:
                turn_had_messages = False
                async for message in self._session.receive():
                    turn_had_messages = True
                    for event in self._map_message(message):
                        yield event
                if not turn_had_messages:
                    break
        except Exception as exc:  # noqa: BLE001 — any transport failure ends the call.
            reason = str(exc)

        # A call cut off mid-sentence still said what it said.
        trailing: list[BridgeEvent] = []
        self._finalize_user(trailing)
        self._finalize_agent(trailing)
        for event in trailing:
            yield event
        yield SessionClosed(reason=reason)

    def _map_message(self, message: Any) -> list[BridgeEvent]:
        events: list[BridgeEvent] = []

        if (usage := getattr(message, "usage_metadata", None)) is not None:
            self._usage = (usage.prompt_token_count, usage.response_token_count)

        content = getattr(message, "server_content", None)
        if content is None:
            return events

        if content.interrupted:
            # The provider already stopped speaking; the runtime still has to flush
            # what the browser has queued. What was said up to here still happened,
            # so it is finalized rather than dropped.
            events.append(SpeechStarted())
            self._finalize_agent(events)

        if (transcription := content.input_transcription) is not None:
            self._user_text += transcription.text or ""
            if transcription.finished:
                self._finalize_user(events)
            else:
                events.append(UserTranscript(text=self._user_text, is_final=False))

        if (transcription := content.output_transcription) is not None:
            # The agent answering *is* the end of the caller's utterance — this
            # provider never flags one itself.
            self._finalize_user(events)
            self._agent_text += transcription.text or ""
            if transcription.finished:
                self._finalize_agent(events)
            else:
                events.append(AgentTranscript(text=self._agent_text, is_final=False))

        if content.model_turn is not None:
            for part in content.model_turn.parts or ():
                if (blob := part.inline_data) is not None and blob.data:
                    # Audio can arrive before its transcription, and is just as much
                    # a sign that the caller has stopped talking.
                    self._finalize_user(events)
                    events.append(AudioDelta(pcm=blob.data))

        if content.turn_complete:
            self._finalize_user(events)
            self._finalize_agent(events)
            input_tokens, output_tokens = self._usage
            self._usage = (None, None)
            events.append(TurnEnded(input_tokens=input_tokens, output_tokens=output_tokens))

        return events

    def _finalize_user(self, events: list[BridgeEvent]) -> None:
        """Close off the caller's utterance, if one is open.

        Gemini streams transcription as fragments and — unlike OpenAI — never sends a
        completed form, so the adapter decides where an utterance ends. Waiting for a
        `finished` flag that never arrives is why nothing the caller said was ever
        finalized, and therefore never reached the transcript or the per-turn hook.
        """
        if not self._user_text:
            return
        events.append(UserTranscript(text=self._user_text, is_final=True))
        self._user_text = ""

    def _finalize_agent(self, events: list[BridgeEvent]) -> None:
        if not self._agent_text:
            return
        events.append(AgentTranscript(text=self._agent_text, is_final=True))
        self._agent_text = ""

    async def close(self) -> None:
        session, self._session = self._session, None
        manager, self._manager = self._manager, None
        try:
            # Unwinding the context manager is what actually closes the socket; the
            # session object has no close of its own on this SDK.
            if manager is not None:
                await manager.__aexit__(None, None, None)
            elif session is not None and hasattr(session, "close"):
                await session.close()
        except Exception as exc:  # noqa: BLE001 — best-effort.
            logger.info("voice.gemini_bridge.close_failed", error=str(exc))
