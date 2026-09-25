"""Who may join an avatar call's room, and how each side addresses LiveKit."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from livekit import api

from assemblix_api.core.settings import get_settings

USER_IDENTITY = "user"
AGENT_IDENTITY = "agent"
AVATAR_IDENTITY = "avatar"
# Lets the avatar's tracks be attributed to the agent (LiveKit avatar convention).
PUBLISH_ON_BEHALF = "lk.publish_on_behalf"


def new_room_name() -> str:
    return f"va-{uuid4().hex}"


def participant_token(
    room: str,
    identity: str,
    *,
    ttl_seconds: int,
    agent: bool = False,
    attributes: dict[str, str] | None = None,
) -> str:
    settings = get_settings()
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_ttl(timedelta(seconds=ttl_seconds))
    )
    if agent:
        token = token.with_kind("agent")
    if attributes:
        token = token.with_attributes(attributes)
    return token.to_jwt()


def ws_url(url: str) -> str:
    return url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)


def http_url(url: str) -> str:
    return url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)
