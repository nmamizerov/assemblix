"""Room teardown. Deleting the room is what ends the vendor's avatar session."""

from __future__ import annotations

import structlog
from livekit import api

from assemblix_api.core.settings import get_settings
from assemblix_api.realtime.livekit.tokens import http_url

logger = structlog.get_logger(__name__)


async def delete_room(room: str) -> None:
    """Idempotent and silent: called from ``finally`` blocks; LiveKit's
    ``empty_timeout`` is the backstop when this fails."""
    settings = get_settings()
    client = api.LiveKitAPI(
        http_url(settings.livekit_url), settings.livekit_api_key, settings.livekit_api_secret
    )
    try:
        await client.room.delete_room(api.DeleteRoomRequest(room=room))
    except Exception as exc:  # noqa: BLE001 — best-effort cleanup.
        logger.warning("livekit.delete_room_failed", room=room, error=str(exc))
    finally:
        await client.aclose()
