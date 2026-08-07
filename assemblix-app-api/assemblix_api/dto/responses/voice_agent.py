"""Pydantic schemas for voice agent responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas.voice_agent import VoiceAgentConfig


class VoiceAgentResponse(DTOModel):
    id: UUID = Field(description="Unique identifier of the voice agent")
    project_id: UUID = Field(description="ID of the owning project")
    name: str = Field(description="Display name")
    description: str | None = Field(default=None, description="Optional description")
    config: VoiceAgentConfig = Field(description="Prompt, voice, knowledge and analysis hooks")
    is_active: bool = Field(description="Whether the agent can accept sessions")
    session_count: int = Field(description="Number of voice sessions started with this agent")
    total_credits: float = Field(description="Total credits consumed by this agent")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
