"""Provider dispatch for starting an avatar inside a LiveKit room we own.

Every avatar vendor that supports LiveKit takes the same inputs — a room URL and a
token — so adding a vendor is one branch here plus one adapter function. Vendors
that need their own attributes on the avatar's token pass them to the factory.
"""

from __future__ import annotations

from collections.abc import Callable

from assemblix_api.external.avatar import anam, bithuman
from assemblix_api.external.avatar.errors import AvatarUnavailable


async def start_vendor_session(
    *,
    provider: str,
    api_key: str,
    avatar_id: str,
    avatar_model: str,
    livekit_url: str,
    room_name: str,
    make_livekit_token: Callable[[dict[str, str]], str],
) -> str:
    if provider == "anam":
        return await anam.start_livekit_session(
            api_key=api_key,
            avatar_id=avatar_id,
            avatar_model=avatar_model,
            livekit_url=livekit_url,
            livekit_token=make_livekit_token({}),
        )
    if provider == "bithuman":
        return await bithuman.start_livekit_session(
            api_key=api_key,
            avatar_id=avatar_id,
            avatar_model=avatar_model,
            livekit_url=livekit_url,
            room_name=room_name,
            make_livekit_token=make_livekit_token,
        )
    raise AvatarUnavailable(f"Avatar provider {provider!r} cannot join LiveKit rooms")
