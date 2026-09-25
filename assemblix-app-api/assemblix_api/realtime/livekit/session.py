"""An avatar call's media room: the agent joins, the vendor joins, the caller joins."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from assemblix_api.core.settings import get_settings
from assemblix_api.external.avatar.errors import AvatarUnavailable
from assemblix_api.external.avatar.livekit_join import start_vendor_session
from assemblix_api.realtime.livekit.avatar_output import AvatarAudioOutput
from assemblix_api.realtime.livekit.rooms import delete_room
from assemblix_api.realtime.livekit.tokens import (
    AGENT_IDENTITY,
    AVATAR_IDENTITY,
    PUBLISH_ON_BEHALF,
    USER_IDENTITY,
    participant_token,
    ws_url,
)
from assemblix_api.services.avatar_service import ResolvedAvatar

logger = structlog.get_logger(__name__)

# rtc.TrackKind values, mirrored so tests need no native library.
KIND_AUDIO = 1
KIND_VIDEO = 2
# The vendor's token must outlive the whole call, not just the join.
_VENDOR_TOKEN_TTL_SECONDS = 2 * 60 * 60
_POLL_SECONDS = 0.1


@dataclass
class AvatarMedia:
    room_name: str
    output: AvatarAudioOutput
    _room: Any
    _mic_track: Any

    async def mic(self, sample_rate: int) -> AsyncIterator[bytes]:
        from livekit import rtc

        stream = rtc.AudioStream(self._mic_track, sample_rate=sample_rate, num_channels=1)
        try:
            async for event in stream:
                yield bytes(event.frame.data)
        finally:
            await stream.aclose()

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._room.disconnect()
        await delete_room(self.room_name)


def _published(room: Any, identity: str, kind: int) -> Any | None:
    participant = room.remote_participants.get(identity)
    if participant is None:
        return None
    for publication in participant.track_publications.values():
        if publication.kind == kind and publication.track is not None:
            return publication.track
    return None


async def _wait_for_both_sides(room: Any) -> Any:
    while True:
        mic = _published(room, USER_IDENTITY, KIND_AUDIO)
        if mic is not None and _published(room, AVATAR_IDENTITY, KIND_VIDEO) is not None:
            return mic
        await asyncio.sleep(_POLL_SECONDS)


def _new_room() -> Any:
    from livekit import rtc

    return rtc.Room()


async def open_avatar_media(
    *,
    room_name: str,
    avatar: ResolvedAvatar,
    timeout: float,
    start_vendor: Callable[..., Awaitable[str]] = start_vendor_session,
    room_factory: Callable[[], Any] | None = None,
) -> AvatarMedia:
    settings = get_settings()
    room = (room_factory or _new_room)()
    try:
        await room.connect(
            ws_url(settings.livekit_url),
            participant_token(room_name, AGENT_IDENTITY, ttl_seconds=60, agent=True),
        )
        output = AvatarAudioOutput(room.local_participant, destination=AVATAR_IDENTITY)
        session_id = await start_vendor(
            provider=avatar.provider,
            api_key=avatar.api_key,
            avatar_id=avatar.avatar_id,
            avatar_model=avatar.avatar_model,
            livekit_url=settings.livekit_public_url,
            livekit_token=participant_token(
                room_name,
                AVATAR_IDENTITY,
                ttl_seconds=_VENDOR_TOKEN_TTL_SECONDS,
                agent=True,
                attributes={PUBLISH_ON_BEHALF: AGENT_IDENTITY},
            ),
        )
        logger.info("avatar.vendor_started", room=room_name, vendor_session_id=session_id)
        try:
            mic_track = await asyncio.wait_for(_wait_for_both_sides(room), timeout)
        except TimeoutError as exc:
            raise AvatarUnavailable("The avatar or the caller did not join in time") from exc
    except BaseException:
        with contextlib.suppress(Exception):
            await room.disconnect()
        await delete_room(room_name)
        raise
    return AvatarMedia(room_name=room_name, output=output, _room=room, _mic_track=mic_track)
