"""open_avatar_media: join, start the vendor, wait for both sides, clean up on failure."""

from typing import Any

import pytest

from assemblix_api.core.settings import get_settings
from assemblix_api.external.avatar.errors import AvatarBusy, AvatarUnavailable
from assemblix_api.realtime.livekit import session as media_module
from assemblix_api.services.avatar_service import ResolvedAvatar

_AVATAR = ResolvedAvatar(provider="anam", api_key="k", avatar_id="av", avatar_model="cara-4")


class _Pub:
    def __init__(self, kind: int, track: Any = object()) -> None:
        self.kind = kind
        self.track = track


class _Remote:
    def __init__(self, pubs: list[_Pub]) -> None:
        self.track_publications = {str(i): p for i, p in enumerate(pubs)}


class _Local:
    def register_rpc_method(self, name: str, handler: Any) -> None: ...


class _Room:
    def __init__(self, participants: dict[str, _Remote]) -> None:
        self.remote_participants = participants
        self.local_participant = _Local()
        self.connected_to: tuple[str, str] | None = None
        self.disconnected = False

    async def connect(self, url: str, token: str) -> None:
        self.connected_to = (url, token)

    async def disconnect(self) -> None:
        self.disconnected = True


@pytest.fixture(autouse=True)
def _livekit(monkeypatch) -> list[str]:
    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_url", "http://livekit:7880")
    monkeypatch.setattr(settings, "livekit_public_url", "wss://rtc.example.com")
    monkeypatch.setattr(settings, "livekit_api_key", "key")
    monkeypatch.setattr(settings, "livekit_api_secret", "s" * 32)
    deleted: list[str] = []

    async def _delete(room: str) -> None:
        deleted.append(room)

    monkeypatch.setattr(media_module, "delete_room", _delete)
    return deleted


def _ready_room() -> _Room:
    return _Room(
        {
            "avatar": _Remote([_Pub(media_module.KIND_VIDEO)]),
            "user": _Remote([_Pub(media_module.KIND_AUDIO)]),
        }
    )


async def test_joins_as_agent_and_starts_the_vendor_with_the_public_url(_livekit) -> None:
    room = _ready_room()
    vendor_calls: list[dict] = []

    async def start_vendor(**kwargs: Any) -> str:
        vendor_calls.append(kwargs)
        return "s-1"

    media = await media_module.open_avatar_media(
        room_name="va-1",
        avatar=_AVATAR,
        timeout=1,
        start_vendor=start_vendor,
        room_factory=lambda: room,
    )

    assert room.connected_to is not None and room.connected_to[0] == "ws://livekit:7880"
    assert vendor_calls[0]["livekit_url"] == "wss://rtc.example.com"
    assert vendor_calls[0]["provider"] == "anam"

    await media.close()
    assert room.disconnected
    assert _livekit == ["va-1"]


async def test_vendor_refusal_cleans_up_and_propagates(_livekit) -> None:
    room = _ready_room()

    async def start_vendor(**kwargs: Any) -> str:
        raise AvatarBusy("429")

    with pytest.raises(AvatarBusy):
        await media_module.open_avatar_media(
            room_name="va-2", avatar=_AVATAR, timeout=1,
            start_vendor=start_vendor, room_factory=lambda: room,
        )
    assert room.disconnected
    assert _livekit == ["va-2"]


async def test_avatar_that_never_shows_up_is_unavailable(_livekit) -> None:
    room = _Room({"user": _Remote([_Pub(media_module.KIND_AUDIO)])})

    async def start_vendor(**kwargs: Any) -> str:
        return "s-3"

    with pytest.raises(AvatarUnavailable):
        await media_module.open_avatar_media(
            room_name="va-3", avatar=_AVATAR, timeout=0.3,
            start_vendor=start_vendor, room_factory=lambda: room,
        )
    assert room.disconnected
    assert _livekit == ["va-3"]
