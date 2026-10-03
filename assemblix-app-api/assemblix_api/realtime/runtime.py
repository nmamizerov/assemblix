"""The voice session runtime: one asyncio task pumping audio both ways.

Constraints that are not negotiable (see CLAUDE.md):

* it never holds a DB connection — everything it needs is passed in;
* it never goes through the Arq queue — audio lives in process memory;
* it takes no application state, only explicit arguments, so the whole runtime
  can move into its own process later without being rewritten.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol

import structlog

from assemblix_api.external.voice.conversation.contract import (
    AgentTranscript,
    AudioDelta,
    BridgeError,
    RealtimeBridge,
    SessionClosed,
    SpeechStarted,
    TurnEnded,
    TurnTimings,
    UserTranscript,
)
from assemblix_api.realtime.hooks import TurnDispatcher
from assemblix_api.realtime.leading_silence import LeadingSilenceMeter

logger = structlog.get_logger(__name__)

_BYTES_PER_SAMPLE = 2
# Per-turn debug data on transcript lines; kept out of what the final hook sees.
_DEBUG_KEYS = ("llmCall", "usage")


class ClientChannel(Protocol):
    """The caller's side of the session, narrowed to what the runtime uses."""

    # "ws": audio rides the WebSocket; "livekit": an avatar call's media room.
    media: str

    async def send_json(self, data: dict) -> None: ...

    async def send_bytes(self, data: bytes) -> None: ...

    async def interrupt_playback(self) -> int | None:
        """Stop server-side playback; return how much of the reply was heard (ms),
        or None when nothing is playing or playback lives in the browser."""
        ...

    async def end_of_utterance(self) -> None: ...

    def __aiter__(self) -> AsyncIterator[bytes | dict]: ...


class VoiceSessionRuntime:
    def __init__(
        self,
        *,
        bridge: RealtimeBridge,
        client: ClientChannel,
        instructions: str,
        voice: str,
        language: str,
        params: dict,
        max_session_sec: float,
        dispatcher: TurnDispatcher | None = None,
        prepare: Callable[[], Awaitable[None]] | None = None,
        on_stopped: Callable[[], Awaitable[None]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bridge = bridge
        self._client = client
        self._instructions = instructions
        self._voice = voice
        self._language = language
        self._params = params
        self._max_session_sec = max_session_sec
        self._dispatcher = dispatcher
        self._prepare = prepare
        self._on_stopped = on_stopped
        self._clock = clock

        # Audio actually forwarded to the browser, in ms. On a barge-in the
        # provider needs to know how much of its answer was really heard.
        self._played_ms = 0
        # Interrupting when the agent is silent makes the provider answer with
        # "no active response found" — a real error event for a non-event.
        self._agent_speaking = False
        # Browser playback of the latest agent turn, by wall clock: TurnEnded arrives
        # once the audio is sent, while the browser may still be playing it.
        self._playback_started_at: float | None = None
        self._playback_ms = 0
        self._playback_open = False
        self._last_inbound_audio_at: float | None = None
        self._pending_timings: TurnTimings | None = None
        self._reply_timings: dict[str, int] | None = None
        # Where the browser's playback of this turn ends if the audio arrives no
        # later; a chunk arriving after it means the caller heard silence.
        self._play_end: float | None = None
        self._gap_max_ms = 0
        self._lead_meter: LeadingSilenceMeter | None = None
        self._lead_ms: int | None = None
        # The mic streams continuously, so without this every later audio packet of a
        # measured turn would emit a second, inbound-audio based timing.
        self._stage_timings_sent = False
        self._transcript: list[dict] = []
        # Where the current turn's lines start; a cascade TurnEnded annotates one of them.
        self._turn_start = 0
        self._closed_reason: str | None = None
        self._turn_index = 0
        # The agent's last finished reply — context the per-turn hook needs, since
        # it sees one utterance rather than the conversation.
        self._last_agent_text: str | None = None
        self._input_tokens = 0
        self._output_tokens = 0
        self._speech_chars = 0
        self._started_at = time.monotonic()

    @property
    def transcript(self) -> list[dict]:
        """Accumulated in memory; persisted once, by the caller, after the call."""
        return self._transcript

    @property
    def usage(self) -> tuple[int, int]:
        """Provider token counts for the whole call — observability, not the charge."""
        return self._input_tokens, self._output_tokens

    @property
    def speech_chars(self) -> int:
        """Characters spoken by a TTS provider — zero on a native-voice call."""
        return self._speech_chars

    @property
    def duration_sec(self) -> float:
        return time.monotonic() - self._started_at

    async def run(self) -> str:
        """Drive the session to completion and return the reason it ended.

        Everything after the pumps stop runs in a ``finally``: by the time a call
        ends the browser is usually already gone — the client sends
        ``session.stop`` and closes the socket in the same tick — and the final
        hook is precisely the thing that has to outlive it.
        """
        connect = self._bridge.connect(
            instructions=self._instructions,
            voice=self._voice,
            language=self._language,
            params=self._params,
        )
        if self._prepare is None:
            await connect
        else:
            # An avatar takes seconds to join; overlap it with the provider handshake.
            # Either side failing must not leave the other running unsupervised.
            connect_task = asyncio.ensure_future(connect)
            prepare_task = asyncio.ensure_future(self._prepare())
            try:
                done, pending = await asyncio.wait(
                    {connect_task, prepare_task}, return_when=asyncio.FIRST_EXCEPTION
                )
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
                for task in done:
                    task.result()
            except BaseException:
                # Covers a failure from either task *and* run() itself being
                # cancelled while awaiting the wait above — asyncio.wait, unlike
                # gather, does not cancel its children on cancellation.
                for task in (connect_task, prepare_task):
                    if not task.done():
                        task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
                with contextlib.suppress(Exception):
                    await self._bridge.close()
                raise
        await self._client.send_json(
            {
                "type": "session.ready",
                "inputSampleRate": self._bridge.input_sample_rate,
                "outputSampleRate": self._bridge.output_sample_rate,
                "media": self._client.media,
            }
        )

        from_client = asyncio.create_task(self._pump_client())
        from_bridge = asyncio.create_task(self._pump_bridge())
        try:
            done, pending = await asyncio.wait(
                {from_client, from_bridge},
                timeout=self._max_session_sec,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                self._closed_reason = "timeout"
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            for task in done:
                task.result()
        finally:
            await self._bridge.close()
            if self._on_stopped is not None:
                # Media teardown must not wait for the final hook, which can run
                # for minutes while an avatar vendor bills for an empty room.
                try:
                    await self._on_stopped()
                except Exception:
                    logger.exception("voice.session.on_stopped_failed")
            reason = self._closed_reason or "completed"

            # Best-effort: a farewell frame nobody is left to receive raises
            # WebSocketDisconnect, and that must not cost the final hook.
            with contextlib.suppress(Exception):
                await self._client.send_json({"type": "session.closed", "reason": reason})

            if self._dispatcher is not None:
                # The one hook that is awaited: the call is already over, and the
                # whole point of the final workflow is that it sees the finished
                # transcript.
                await self._dispatcher.dispatch_final(
                    transcript=[
                        {k: v for k, v in line.items() if k not in _DEBUG_KEYS}
                        for line in self._transcript
                    ],
                    duration_sec=self.duration_sec,
                    end_reason=reason,
                )
        return reason

    async def _pump_client(self) -> None:
        async for frame in self._client:
            if isinstance(frame, bytes):
                self._last_inbound_audio_at = time.monotonic()
                await self._bridge.send_audio(frame)
            elif frame.get("type") == "session.stop":
                self._closed_reason = "user_hangup"
                return

    async def _pump_bridge(self) -> None:
        async for event in self._bridge.events():
            match event:
                case AudioDelta():
                    self._agent_speaking = True
                    chunk_ms = len(event.pcm) // (
                        _BYTES_PER_SAMPLE * self._bridge.output_sample_rate // 1000
                    )
                    self._played_ms += chunk_ms
                    now = self._clock()
                    if self._pending_timings is not None:
                        self._lead_meter = LeadingSilenceMeter(self._bridge.output_sample_rate)
                        self._lead_ms = None
                    self._measure_lead_silence(event.pcm)
                    if not self._playback_open:
                        self._playback_open = True
                        self._playback_started_at = now
                        self._playback_ms = 0
                        self._play_end = None
                        self._gap_max_ms = 0
                    self._playback_ms += chunk_ms
                    self._track_gap(now, chunk_ms)
                    await self._client.send_bytes(event.pcm)
                    await self._emit_timings()
                case UserTranscript():
                    await self._on_transcript("user", event.text, event.is_final)
                case AgentTranscript():
                    await self._on_transcript("assistant", event.text, event.is_final)
                case SpeechStarted():
                    # Two-sided barge-in: playback stops and the provider truncates to
                    # what was actually heard. Playback can outlive generation (an
                    # avatar speaks in real time), so the channel reports it first.
                    await self._client.send_json({"type": "speech.started"})
                    heard_ms = await self._client.interrupt_playback()
                    if heard_ms is not None:
                        await self._bridge.interrupt(audio_end_ms=heard_ms)
                    elif self._late_interrupts():
                        heard_ms = self._heard_ms()
                        if heard_ms is not None and (
                            self._agent_speaking or heard_ms < self._playback_ms
                        ):
                            await self._bridge.interrupt(audio_end_ms=heard_ms)
                    elif self._agent_speaking:
                        await self._bridge.interrupt(audio_end_ms=self._played_ms)
                    self._agent_speaking = False
                    self._played_ms = 0
                    self._playback_open = False
                    self._playback_started_at = None
                    self._lead_meter = None
                case TurnEnded():
                    self._pending_timings = None
                    self._stage_timings_sent = False
                    await self._client.end_of_utterance()
                    self._finish_lead_silence()
                    self._agent_speaking = False
                    self._played_ms = 0
                    self._playback_open = False
                    self._input_tokens += event.input_tokens or 0
                    self._output_tokens += event.output_tokens or 0
                    self._speech_chars += event.speech_chars or 0
                    self._attach_turn_record(event)
                case TurnTimings():
                    self._pending_timings = event
                case BridgeError():
                    logger.warning(
                        "voice.session.bridge_error",
                        code=event.code,
                        message=event.message,
                        is_fatal=event.is_fatal,
                    )
                    await self._client.send_json(
                        {
                            "type": "error",
                            "code": event.code,
                            "message": event.message,
                            "isFatal": event.is_fatal,
                        }
                    )
                    if event.is_fatal:
                        self._closed_reason = "error"
                        return
                case SessionClosed():
                    self._closed_reason = event.reason
                    return

    def _measure_lead_silence(self, pcm: bytes) -> None:
        meter = self._lead_meter
        if meter is None:
            return
        meter.feed(pcm)
        if meter.result_ms is not None:
            self._finish_lead_silence()

    def _finish_lead_silence(self) -> None:
        meter = self._lead_meter
        if meter is None:
            return
        self._lead_meter = None
        self._lead_ms = meter.result_ms if meter.result_ms is not None else meter.silence_ms
        logger.info("voice.cascade.tts_leading_silence", ttsLeadingSilenceMs=self._lead_ms)
        line = next(
            (
                line
                for line in reversed(self._transcript[self._turn_start :])
                if line["role"] == "assistant" and "timings" in line
            ),
            None,
        )
        if line is not None:
            self._add_lead_silence(line["timings"])

    def _add_lead_silence(self, timings: dict) -> None:
        if self._lead_ms is None or "ttsLeadingSilenceMs" in timings:
            return
        timings["ttsLeadingSilenceMs"] = self._lead_ms
        if isinstance(timings.get("ttsFirstAudioMs"), int):
            timings["ttsFirstAudibleMs"] = timings["ttsFirstAudioMs"] + self._lead_ms

    def _attach_turn_record(self, event: TurnEnded) -> None:
        """Put the turn's LLM call and spend on its reply — or, if the brain produced
        none, on the user line it answered."""
        lines = self._transcript[self._turn_start :]
        self._turn_start = len(self._transcript)
        if event.llm_call is None and event.usage is None:
            return
        target = next((line for line in reversed(lines) if line["role"] == "assistant"), None)
        if target is None:
            target = next((line for line in reversed(lines) if line["role"] == "user"), None)
        if target is None:
            return
        if event.llm_call is not None:
            target["llmCall"] = event.llm_call
        if event.usage is not None:
            target["usage"] = event.usage

    def _track_gap(self, now: float, chunk_ms: int) -> None:
        if self._play_end is not None and now > self._play_end:
            self._gap_max_ms = max(self._gap_max_ms, round((now - self._play_end) * 1000))
        start = now if self._play_end is None else max(self._play_end, now)
        self._play_end = start + chunk_ms / 1000

    def _late_interrupts(self) -> bool:
        return self._client.media == "ws" and bool(
            getattr(self._bridge, "accepts_late_interrupt", False)
        )

    def _heard_ms(self) -> int | None:
        """How much of the latest turn the browser has played, assuming it started
        at the first chunk and plays without stalls."""
        if self._playback_started_at is None:
            return None
        elapsed_ms = round((self._clock() - self._playback_started_at) * 1000)
        return min(self._playback_ms, elapsed_ms)

    async def _emit_timings(self) -> None:
        """Last inbound audio → first audio back; per stage when the bridge measured them."""
        stages = self._pending_timings
        if stages is not None:
            self._pending_timings = None
            self._last_inbound_audio_at = None
            self._stage_timings_sent = True
            total = int((time.monotonic() - stages.speech_ended_at) * 1000)
            timings = {
                "eouMs": stages.eou_ms,
                "sttFinalMs": stages.stt_final_ms,
                "brainFirstTokenMs": stages.brain_first_token_ms,
                "ttsFirstAudioMs": max(
                    0, total - stages.eou_ms - stages.stt_final_ms - stages.brain_first_token_ms
                ),
                "totalMs": total,
                "firstAudioMs": total,
            }
            self._reply_timings = timings
            logger.info("voice.cascade.turn", **timings)
            await self._client.send_json({"type": "turn.timings", **timings})
            return
        if self._stage_timings_sent or self._last_inbound_audio_at is None:
            return
        first_audio_ms = int((time.monotonic() - self._last_inbound_audio_at) * 1000)
        self._last_inbound_audio_at = None
        await self._client.send_json({"type": "turn.timings", "firstAudioMs": first_audio_ms})

    async def _on_transcript(self, role: str, text: str, is_final: bool) -> None:
        if is_final:
            line: dict = {"role": role, "text": text}
            if role == "assistant" and self._reply_timings is not None:
                line["timings"] = {**self._reply_timings, "ttsGapMaxMs": self._gap_max_ms}
                self._add_lead_silence(line["timings"])
                self._reply_timings = None
            self._transcript.append(line)
            if role == "assistant":
                self._last_agent_text = text
            elif self._dispatcher is not None:
                # Fire-and-forget: the conversation must not wait for the graph.
                self._dispatcher.dispatch_turn(
                    user_text=text,
                    agent_reply=self._last_agent_text,
                    turn_index=self._turn_index,
                )
                self._turn_index += 1
        await self._client.send_json(
            {"type": "transcript", "role": role, "text": text, "isFinal": is_final}
        )
