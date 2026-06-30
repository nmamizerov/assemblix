"""Response DTO for the `/api/config` server settings endpoint."""

from __future__ import annotations

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class ServerConfigResponse(DTOModel):
    """Server settings the frontend needs before rendering provider-gated UI."""

    system_api_keys: dict[str, bool] = Field(
        description=(
            "Whether a system-level API key is configured per provider "
            "(keys are provider identifiers, e.g. 'openai', 'gemini'). "
            "Providers without one are hidden in the agent node."
        ),
    )
    billing_enabled: bool = Field(
        description="Whether paid billing/payments are enabled on this server.",
    )
