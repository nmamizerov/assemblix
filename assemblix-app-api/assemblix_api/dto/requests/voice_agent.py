"""Pydantic schemas for voice agent requests."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas.voice_agent import VoiceAgentConfig


class VoiceAgentCreateRequest(DTOModel):
    project_id: UUID | None = Field(
        None,
        description="ID of the project; omit when using a project-scoped API key",
    )
    name: str = Field(..., min_length=1, max_length=255, description="Voice agent name")
    description: str | None = Field(
        default=None, max_length=1000, description="Optional description"
    )
    config: VoiceAgentConfig = Field(..., description="Prompt, voice, knowledge and analysis hooks")


class VoiceAgentUpdateRequest(DTOModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    config: VoiceAgentConfig | None = Field(
        default=None, description="Full config replacement; omit to leave unchanged"
    )
    is_active: bool | None = None
