"""Pydantic schemas for voice session responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class VoiceSessionTokenResponse(DTOModel):
    token: str = Field(description="Short-lived token authorizing one voice session")
    expires_in: int = Field(description="Token lifetime in seconds")


class VoiceSessionResponse(DTOModel):
    """One call, as it appears in an agent's history."""

    id: UUID = Field(description="Unique identifier of the session")
    voice_agent_id: UUID = Field(description="Agent that was called")
    status: str = Field(description="active | completed | failed")
    started_at: datetime = Field(description="When the call started")
    ended_at: datetime | None = Field(default=None, description="When the call ended")
    duration_sec: float = Field(description="Call wall-clock duration")
    # Serialized as a JSON number over a Numeric(20, 8) column, matching every other
    # credit field in the API. See assemblix-app-api/CLAUDE.md on why.
    total_credits: float = Field(description="Credits the call consumed")
    turn_count: int = Field(description="Number of transcript lines")
    end_reason: str | None = Field(default=None, description="user_hangup | timeout | error")


class VoiceSessionTranscriptLine(DTOModel):
    role: str = Field(description="user | assistant")
    text: str = Field(description="What was said")


class VoiceSessionExecutionResponse(DTOModel):
    """One analysis-hook run started by this call."""

    id: UUID = Field(description="Execution ID")
    workflow_id: UUID = Field(description="Workflow that ran")
    status: str = Field(description="Execution status")
    started_at: datetime | None = Field(default=None, description="When the run started")
    total_credits: float = Field(description="Credits the run consumed")


class VoiceSessionDetailResponse(VoiceSessionResponse):
    transcript: list[VoiceSessionTranscriptLine] = Field(description="The whole conversation")
    input_tokens: int = Field(description="Provider input tokens, for invoice reconciliation")
    output_tokens: int = Field(description="Provider output tokens, for invoice reconciliation")
    executions: list[VoiceSessionExecutionResponse] = Field(
        description="Analysis-hook runs linked to this call"
    )
