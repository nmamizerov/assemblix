"""Pydantic schemas for voice session responses."""

from __future__ import annotations

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class VoiceSessionTokenResponse(DTOModel):
    token: str = Field(description="Short-lived token authorizing one voice session")
    expires_in: int = Field(description="Token lifetime in seconds")
