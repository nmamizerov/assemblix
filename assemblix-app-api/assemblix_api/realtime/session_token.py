"""Short-lived tokens authorizing one voice session.

The browser cannot carry a JWT in a WebSocket handshake header, so the client
first calls an authenticated HTTP endpoint and receives a token scoped to a
single voice agent. The token is signed with the app's JWT secret and lives for
about a minute — long enough to open the socket, useless afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from assemblix_api.core.settings import get_settings

_PURPOSE = "voice_session"


class InvalidSessionToken(Exception):
    """The token is malformed, expired, or not a voice-session token."""


@dataclass(frozen=True)
class SessionScope:
    """What one session token authorizes."""

    voice_agent_id: UUID
    project_id: UUID
    # A call placed from the editor is a rehearsal; one placed by a program
    # through a project API key is a real call in someone's product.
    is_debug: bool


def mint_session_token(
    *,
    voice_agent_id: UUID,
    project_id: UUID,
    is_debug: bool,
    ttl_seconds: int = 60,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "purpose": _PURPOSE,
        "agent": str(voice_agent_id),
        "project": str(project_id),
        "debug": is_debug,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_session_token(token: str) -> SessionScope:
    """Return what the token authorizes.

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
        return SessionScope(
            voice_agent_id=UUID(payload["agent"]),
            project_id=UUID(payload["project"]),
            is_debug=bool(payload.get("debug", False)),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidSessionToken("Token is missing its scope") from exc
