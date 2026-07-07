"""Fake ElevenLabs stream-input WS for tests — mirrors mock_llm.

`mock_tts_ws` arms a scripted list of received audio messages (base64 audio + alignment).
The connect factory it returns is injected into RealtimeTTSSession via its `connect=`
argument, so no network is touched. The fake terminates the stream the way the real server
does — a final message with empty audio and ``isFinal: true`` — so the session's recv loop
ends cleanly (spike-confirmed protocol).
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest


class ConnectionClosedOK(Exception):
    """Stand-in for websockets.ConnectionClosedOK (raised only if isFinal is never read)."""


class FakeTTSWebSocket:
    def __init__(self, scripted: list[dict[str, Any]]):
        self.sent: list[dict[str, Any]] = []
        self._scripted = list(scripted)
        self._final_sent = False
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        if self._scripted:
            return json.dumps(self._scripted.pop(0))
        if not self._final_sent:
            self._final_sent = True
            return json.dumps({"audio": "", "isFinal": True})
        raise ConnectionClosedOK()

    async def close(self) -> None:
        self.closed = True


class TTSWSMock:
    def __init__(self) -> None:
        self.socket: FakeTTSWebSocket | None = None
        self._scripted: list[dict[str, Any]] = []

    def script_audio(self, chunks: list[tuple[bytes, dict | None]]) -> "TTSWSMock":
        """Arm received messages: each (pcm_bytes, alignment_dict|None)."""
        self._scripted = [
            {
                "audio": base64.b64encode(pcm).decode("ascii"),
                "normalizedAlignment": alignment,
                "isFinal": False,
            }
            for pcm, alignment in chunks
        ]
        return self

    async def connect(self, *args: Any, **kwargs: Any) -> FakeTTSWebSocket:
        self.socket = FakeTTSWebSocket(self._scripted)
        return self.socket


@pytest.fixture
def mock_tts_ws() -> TTSWSMock:
    return TTSWSMock()
