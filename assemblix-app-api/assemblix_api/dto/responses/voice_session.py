"""Pydantic schemas for voice session responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class VoiceSessionMedia(DTOModel):
    """Where an avatar call's audio and video flow. Joined before the WS is opened."""

    transport: Literal["livekit"]
    url: str
    token: str


class VoiceSessionTokenResponse(DTOModel):
    token: str = Field(description="Short-lived token authorizing one voice session")
    expires_in: int = Field(description="Token lifetime in seconds")
    media: VoiceSessionMedia | None = Field(
        default=None, description="LiveKit room to join for an avatar call; absent for plain voice"
    )


class VoiceSessionResponse(DTOModel):
    """One call, as it appears in an agent's history."""

    id: UUID = Field(description="Unique identifier of the session")
    voice_agent_id: UUID = Field(description="Agent that was called")
    client_id: str | None = Field(
        default=None, description="External client identifier this call was tied to"
    )
    status: str = Field(description="active | completed | failed")
    started_at: datetime = Field(description="When the call started")
    ended_at: datetime | None = Field(default=None, description="When the call ended")
    duration_sec: float = Field(description="Call wall-clock duration")
    # Serialized as a JSON number over a Numeric(20, 8) column, matching every other
    # credit field in the API. See assemblix-app-api/CLAUDE.md on why.
    total_credits: float = Field(description="Credits the call consumed")
    own_key_cost_usd: float = Field(
        description="USD spent on the caller's own provider keys (never billed as credits)"
    )
    turn_count: int = Field(description="Number of transcript lines")
    end_reason: str | None = Field(default=None, description="user_hangup | timeout | error")


class VoiceSessionLlmMessage(DTOModel):
    role: str = Field(description="user | assistant")
    content: str = Field(description="Message text as sent to the model")


class VoiceSessionLlmCall(DTOModel):
    """One cascade brain call: what was sent to the LLM and what came back."""

    provider: str | None = Field(default=None, description="LLM provider")
    model: str | None = Field(default=None, description="Model requested")
    effective_model: str | None = Field(default=None, description="Model that answered")
    params: dict[str, Any] = Field(default_factory=dict, description="Model params passed")
    messages: list[VoiceSessionLlmMessage] = Field(
        default_factory=list,
        description="Messages sent, system instructions excluded (see callDetails)",
    )
    response: str = Field(default="", description="Reply text the model produced")
    input_tokens: int = Field(default=0, description="Prompt tokens")
    output_tokens: int = Field(default=0, description="Completion tokens")
    cached_input_tokens: int | None = Field(default=None, description="Cached prompt tokens")
    cost_usd: float = Field(default=0.0, description="LLM cost of the call, USD")
    ttft_ms: int | None = Field(default=None, description="Time to first token (ms)")
    duration_ms: int | None = Field(default=None, description="Whole call duration (ms)")
    outcome: str = Field(description="ok | cancelled | brain_timeout | brain_failed")
    error: str | None = Field(default=None, description="Failure message")


class VoiceSessionTurnUsage(DTOModel):
    """What one cascade turn spent per stage."""

    stt_seconds: float | None = Field(default=None, description="Audio sent to STT (s)")
    stt_cost_usd_estimate: float | None = Field(
        default=None,
        description="Estimated STT cost, USD — STT is billed per stream in 15 s units",
    )
    llm_cost_usd: float | None = Field(default=None, description="LLM cost, USD")
    tts_chars: int | None = Field(default=None, description="Characters synthesized")
    tts_cost_usd: float | None = Field(default=None, description="TTS cost, USD")


class VoiceSessionTranscriptLine(DTOModel):
    role: str = Field(description="user | assistant")
    text: str = Field(description="What was said")
    timings: dict[str, int] | None = Field(
        default=None, description="Cascade stage durations (ms) of the turn this reply ended"
    )
    llm_call: VoiceSessionLlmCall | None = Field(
        default=None, description="The LLM call behind this cascade turn"
    )
    usage: VoiceSessionTurnUsage | None = Field(
        default=None, description="Per-stage spend of this cascade turn"
    )


class VoiceSessionStageConfig(DTOModel):
    provider: str | None = Field(default=None, description="Provider of the stage")
    model: str | None = Field(default=None, description="Model of the stage")


class VoiceSessionBrainConfig(VoiceSessionStageConfig):
    params: dict[str, Any] = Field(default_factory=dict, description="Model params")
    history_turns: int | None = Field(default=None, description="History window size")


class VoiceSessionStageCosts(DTOModel):
    """Whole-call spend per cascade stage, as billed."""

    stt_seconds: float | None = Field(default=None, description="STT seconds billed")
    stt_cost_usd: float | None = Field(default=None, description="STT cost, USD")
    llm_cost_usd: float | None = Field(default=None, description="LLM cost, USD")
    tts_chars: int | None = Field(default=None, description="Characters synthesized")
    tts_cost_usd: float | None = Field(default=None, description="TTS cost, USD")
    platform_fee_credits: float | None = Field(default=None, description="Platform fee, credits")
    provider_margin_credits: float | None = Field(
        default=None, description="Provider usage on system keys, credits"
    )


class VoiceSessionCallDetails(DTOModel):
    """What a cascade call ran with, stored once per call."""

    instructions: str = Field(default="", description="System instructions of every turn")
    stt: VoiceSessionStageConfig | None = Field(default=None, description="STT stage")
    brain: VoiceSessionBrainConfig | None = Field(default=None, description="LLM stage")
    tts: VoiceSessionStageConfig | None = Field(default=None, description="TTS stage")
    costs: VoiceSessionStageCosts | None = Field(default=None, description="Spend per stage")


class VoiceSessionExecutionResponse(DTOModel):
    """One analysis-hook run started by this call."""

    id: UUID = Field(description="Execution ID")
    workflow_id: UUID = Field(description="Workflow that ran")
    status: str = Field(description="Execution status")
    started_at: datetime | None = Field(default=None, description="When the run started")
    total_credits: float = Field(description="Credits the run consumed")
    own_key_cost_usd: float | None = Field(
        default=None,
        description="USD the run cost on the caller's own provider keys",
    )


class VoiceSessionDetailResponse(VoiceSessionResponse):
    transcript: list[VoiceSessionTranscriptLine] = Field(description="The whole conversation")
    input_tokens: int = Field(description="Provider input tokens, for invoice reconciliation")
    output_tokens: int = Field(description="Provider output tokens, for invoice reconciliation")
    executions: list[VoiceSessionExecutionResponse] = Field(
        description="Analysis-hook runs linked to this call"
    )
    timing_summary: dict[str, dict[str, int]] | None = Field(
        default=None, description="p50/p95 per cascade stage (ms); null for realtime calls"
    )
    call_details: VoiceSessionCallDetails | None = Field(
        default=None, description="Cascade instructions, stage config and costs; null otherwise"
    )
