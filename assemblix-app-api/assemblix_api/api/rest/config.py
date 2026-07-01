"""
Server config endpoint.

Exposes the handful of server settings the frontend needs to adapt its UI —
most importantly which LLM providers have a system API key configured. The UI
hides providers without one (the server can't call them), so this keeps the
agent-node provider list honest. Only booleans are exposed, never key values.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import get_current_user
from assemblix_api.dto.responses.config import ServerConfigResponse

router = APIRouter(prefix="/config", tags=["Config"])

# Provider identifier -> Settings attribute holding its system API key.
_SYSTEM_KEY_BY_PROVIDER: dict[str, str] = {
    "openai": "system_openai_api_key",
    "gemini": "system_gemini_api_key",
    "deepseek": "system_deepseek_api_key",
}


@router.get("", response_model=ServerConfigResponse)
async def get_config(
    current_user: User = Depends(get_current_user),
) -> ServerConfigResponse:
    """Return server settings (system-key presence per provider, feature flags)."""
    settings = get_settings()
    return ServerConfigResponse(
        system_api_keys={
            provider: bool(getattr(settings, attr))
            for provider, attr in _SYSTEM_KEY_BY_PROVIDER.items()
        },
        billing_enabled=settings.billing_enabled,
    )
