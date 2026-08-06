"""Short-lived tokens authorizing one voice session.

The browser cannot carry a JWT in a WebSocket handshake header, so the client
first calls an authenticated HTTP endpoint and receives a token scoped to a
single voice agent. The token is signed with the app's JWT secret and lives for
about a minute — long enough to open the socket, useless afterwards.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from assemblix_api.core.settings import get_settings

_PURPOSE = "voice_session"


class InvalidSessionToken(Exception):
    """The token is malformed, expired, or not a voice-session token."""


def mint_session_token(*, voice_agent_id: UUID, project_id: UUID, ttl_seconds: int = 60) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "purpose": _PURPOSE,
        "agent": str(voice_agent_id),
        "project": str(project_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_session_token(token: str) -> tuple[UUID, UUID]:
    """Return ``(voice_agent_id, project_id)``.

    Raises:
        InvalidSessionToken: expired, malformed, or issued for another purpose.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidSessionToken(str(exc)) from exc

    if payload.get("purpose") != _PURPOSE:
        raise InvalidSessionToken("Token was not issued for a voice session")
    try:
        return UUID(payload["agent"]), UUID(payload["project"])
    except (KeyError, ValueError) as exc:
        raise InvalidSessionToken("Token is missing its scope") from exc
