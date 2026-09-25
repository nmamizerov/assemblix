"""Provider dispatch for starting an avatar inside a LiveKit room we own.

Every avatar vendor that supports LiveKit takes the same inputs — a room URL and a
token — so adding a vendor is one branch here plus one adapter function.
"""

from __future__ import annotations

from assemblix_api.external.avatar import anam
from assemblix_api.external.avatar.errors import AvatarUnavailable


async def start_vendor_session(
    *,
    provider: str,
    api_key: str,
    avatar_id: str,
    avatar_model: str,
    livekit_url: str,
    livekit_token: str,
) -> str:
    if provider == "anam":
        return await anam.start_livekit_session(
            api_key=api_key,
            avatar_id=avatar_id,
            avatar_model=avatar_model,
            livekit_url=livekit_url,
            livekit_token=livekit_token,
        )
    raise AvatarUnavailable(f"Avatar provider {provider!r} cannot join LiveKit rooms")
