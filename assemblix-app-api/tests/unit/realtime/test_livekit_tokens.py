"""LiveKit tokens carry exactly the grants a participant needs."""

import jwt

from assemblix_api.core.settings import get_settings
from assemblix_api.realtime.livekit import rooms
from assemblix_api.realtime.livekit.tokens import (
    AGENT_IDENTITY,
    AVATAR_IDENTITY,
    PUBLISH_ON_BEHALF,
    http_url,
    new_room_name,
    participant_token,
    ws_url,
)

_SECRET = "s" * 32


def _configure(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_url", "http://livekit:7880")
    monkeypatch.setattr(settings, "livekit_public_url", "wss://rtc.example.com")
    monkeypatch.setattr(settings, "livekit_api_key", "key")
    monkeypatch.setattr(settings, "livekit_api_secret", _SECRET)


def test_room_names_are_unique_and_prefixed() -> None:
    first, second = new_room_name(), new_room_name()
    assert first.startswith("va-") and len(first) == 35
    assert first != second


def test_avatar_token_is_scoped_to_one_room_and_publishes_for_the_agent(monkeypatch) -> None:
    _configure(monkeypatch)
    token = participant_token(
        "va-1",
        AVATAR_IDENTITY,
        ttl_seconds=60,
        agent=True,
        attributes={PUBLISH_ON_BEHALF: AGENT_IDENTITY},
    )
    claims = jwt.decode(token, _SECRET, algorithms=["HS256"])

    assert claims["sub"] == "avatar"
    assert claims["iss"] == "key"
    assert claims["kind"] == "agent"
    assert claims["video"]["room"] == "va-1"
    assert claims["video"]["roomJoin"] is True
    assert claims["attributes"] == {"lk.publish_on_behalf": "agent"}
    assert claims["exp"] - claims["nbf"] == 60


def test_user_token_is_not_an_agent(monkeypatch) -> None:
    _configure(monkeypatch)
    claims = jwt.decode(
        participant_token("va-1", "user", ttl_seconds=60), _SECRET, algorithms=["HS256"]
    )
    assert claims["sub"] == "user"
    assert claims.get("kind") != "agent"


def test_url_schemes_are_normalized_for_each_client() -> None:
    assert ws_url("http://livekit:7880") == "ws://livekit:7880"
    assert ws_url("https://rtc.example.com") == "wss://rtc.example.com"
    assert ws_url("wss://rtc.example.com") == "wss://rtc.example.com"
    assert http_url("wss://rtc.example.com") == "https://rtc.example.com"
    assert http_url("ws://livekit:7880") == "http://livekit:7880"
    assert http_url("http://livekit:7880") == "http://livekit:7880"


async def test_delete_room_swallows_failures(monkeypatch) -> None:
    _configure(monkeypatch)

    class _Boom:
        def __init__(self, *args, **kwargs) -> None:
            self.room = self

        async def delete_room(self, request) -> None:
            raise RuntimeError("livekit down")

        async def aclose(self) -> None: ...

    monkeypatch.setattr(rooms.api, "LiveKitAPI", _Boom)
    await rooms.delete_room("va-1")  # must not raise
