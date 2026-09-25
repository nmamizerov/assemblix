"""The voice-session WebSocket: every avatar-call failure reaches the caller with a reason."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from assemblix_api.api.rest import voice_sessions
from assemblix_api.external.avatar.errors import AvatarBusy
from assemblix_api.external.voice.conversation.contract import SessionClosed
from assemblix_api.realtime.livekit import session as livekit_session
from assemblix_api.realtime.session_token import mint_session_token

_ROOM = "va-x"
_AVATAR = SimpleNamespace(provider="anam", api_key="k", avatar_id="a", avatar_model="m")


class _Bridge:
    input_sample_rate = 24000
    output_sample_rate = 24000

    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def connect(self, **kwargs: Any) -> None: ...

    async def send_audio(self, pcm: bytes) -> None: ...

    async def interrupt(self, *, audio_end_ms: int) -> None: ...

    def events(self) -> AsyncIterator[Any]:
        async def _iter() -> AsyncIterator[Any]:
            for event in self._events:
                yield event

        return _iter()

    async def close(self) -> None: ...


class _Output:
    async def push(self, pcm: bytes, sample_rate: int) -> None: ...

    async def interrupt(self) -> int | None:
        return None

    async def end_utterance(self) -> None: ...


class _Media:
    def __init__(self) -> None:
        self.output = _Output()
        self.closes = 0

    async def mic(self, sample_rate: int) -> AsyncIterator[bytes]:
        await asyncio.sleep(3600)
        yield b""

    async def close(self) -> None:
        self.closes += 1


def _setup(avatar: Any) -> SimpleNamespace:
    return SimpleNamespace(
        instructions="i",
        voice="alloy",
        language="ru",
        params={},
        provider="openai",
        model="gpt-realtime",
        api_key="k",
        api_base=None,
        tts=None,
        turn_workflow_id=None,
        final_workflow_id=None,
        cost_per_minute=0.0,
        uses_system_key=False,
        avatar=avatar,
    )


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(
        avatar=_AVATAR,
        bridge_events=[SessionClosed(reason="completed")],
        open_media=None,
        closed_sessions=[],
        deleted_rooms=[],
    )

    async def load_setup(**kwargs: Any) -> Any:
        return _setup(state.avatar)

    async def open_session(**kwargs: Any) -> Any:
        return uuid4()

    async def close_session(**kwargs: Any) -> None:
        state.closed_sessions.append(kwargs)

    async def delete_room(room: str) -> None:
        state.deleted_rooms.append(room)

    async def open_avatar_media(**kwargs: Any) -> Any:
        return await state.open_media(**kwargs)

    monkeypatch.setattr(voice_sessions, "load_voice_session_setup", load_setup)
    monkeypatch.setattr(voice_sessions, "open_voice_session", open_session)
    monkeypatch.setattr(voice_sessions, "close_voice_session", close_session)
    monkeypatch.setattr(voice_sessions, "delete_room", delete_room)
    monkeypatch.setattr(
        voice_sessions, "create_bridge", lambda **kwargs: _Bridge(state.bridge_events)
    )
    monkeypatch.setattr(livekit_session, "open_avatar_media", open_avatar_media)
    return state


def _call(room: str | None = _ROOM) -> list[dict]:
    """Open the stream, collect every JSON frame until the server closes it."""
    app = FastAPI()
    app.include_router(voice_sessions.router)
    token = mint_session_token(
        voice_agent_id=uuid4(), project_id=uuid4(), is_debug=True, room=room
    )
    frames: list[dict] = []
    with TestClient(app).websocket_connect(f"/voice-agents/sessions/{token}/stream") as ws:
        while True:
            message = ws.receive()
            if message["type"] == "websocket.close":
                break
            if message.get("text") is not None:
                frames.append(json.loads(message["text"]))
    return frames


def _closed_reasons(frames: list[dict]) -> list[str]:
    return [f["reason"] for f in frames if f["type"] == "session.closed"]


def test_vendor_concurrency_limit_is_reported_as_busy(harness: SimpleNamespace) -> None:
    # Arrange
    async def busy(**kwargs: Any) -> Any:
        raise AvatarBusy("concurrent_limit")

    harness.open_media = busy

    # Act
    frames = _call()

    # Assert
    assert _closed_reasons(frames) == ["avatar_busy"]
    assert harness.closed_sessions[0]["end_reason"] == "error"


def test_any_other_avatar_failure_is_reported_as_unavailable(harness: SimpleNamespace) -> None:
    # Arrange
    async def broken(**kwargs: Any) -> Any:
        raise RuntimeError("could not connect to LiveKit")

    harness.open_media = broken

    # Act
    frames = _call()

    # Assert
    assert _closed_reasons(frames) == ["avatar_unavailable"]
    assert harness.closed_sessions[0]["end_reason"] == "error"


def test_avatar_token_for_an_agent_without_avatar_deletes_the_room(
    harness: SimpleNamespace,
) -> None:
    # Arrange
    harness.avatar = None

    # Act
    frames = _call()

    # Assert
    assert _closed_reasons(frames) == ["avatar_unavailable"]
    assert harness.deleted_rooms == [_ROOM]


def test_a_finished_avatar_call_closes_its_media_once(harness: SimpleNamespace) -> None:
    # Arrange
    media = _Media()

    async def opened(**kwargs: Any) -> Any:
        return media

    harness.open_media = opened

    # Act
    frames = _call()

    # Assert
    assert _closed_reasons(frames) == ["completed"]
    assert media.closes == 1
    assert harness.closed_sessions[0]["end_reason"] == "completed"
    assert harness.closed_sessions[0]["tts_cost_usd"] == Decimal(0)
