"""Unit tests for audio turns on the AGENT node.

Covers the two branches of Task 6: an audio turn on an audio-capable model
(``accepts_audio=True``) sends the raw audio as an LLM content part instead of
transcribing it first, and an audio turn on a non-audio model raises a clear
``ValueError`` instead of silently dropping the audio.
"""

from __future__ import annotations

import types
from typing import Any

import pytest

from assemblix_api.enums import PlanTier
from assemblix_api.nodes.agent_node import AgentNode
from assemblix_api.schemas.execution import AudioInput

from ._helpers import build_node, make_context, node_input


class _FakeResolver:
    """Stand-in for CredentialResolver: returns a fixed (api_key, is_system_key)."""

    async def resolve(self, **_kwargs: object) -> tuple[str, bool]:
        return "sk-test", True


def _fake_creds(_mocker: Any) -> dict[str, Any]:
    """Credential wiring kwargs mirroring test_agent_node.py's fake-resolver pattern."""
    return {
        "credential_service": types.SimpleNamespace(),  # non-None; resolver bypasses it
        "credential_resolver": _FakeResolver(),
        "organization_plan": PlanTier.PRO,
    }


def _content_parts(messages: list[dict]) -> list[dict]:
    """Flatten any list-typed ``content`` across messages into a flat list of parts."""
    parts: list[dict] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            parts.extend(p for p in content if isinstance(p, dict))
    return parts


def _agent(model: str, provider: str = "gemini", audio_input: str | None = None) -> AgentNode:
    config: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "instructions": [{"role": "user", "content": "answer the user"}],
        "responseFormat": "text",
    }
    if audio_input is not None:
        config["audioInput"] = audio_input
    return build_node(AgentNode, "agent", config)


async def test_audio_turn_sends_audio_part_to_gemini(mock_llm, mocker) -> None:
    # Arrange
    mock_llm.set_response("hi there")
    audio = AudioInput(bytes=b"RIFFwav", mime="audio/wav", filename="voice.wav")
    context = make_context(
        input_data={"input_type": "audio"},
        audio_input=audio,
        chat_history=[{"role": "user", "content": ""}],
        **_fake_creds(mocker),
    )
    node = _agent("gemini-3-flash-preview")
    # Act
    await node.execute(node_input({"input_type": "audio"}, context))
    # Assert
    messages = mock_llm.calls[0]["messages"]
    parts = _content_parts(messages)
    assert any(p.get("type") in {"input_audio", "audio", "file"} for p in parts)


async def test_audio_turn_on_non_audio_model_raises(mocker) -> None:
    # Arrange
    audio = AudioInput(bytes=b"RIFF", mime="audio/wav", filename="voice.wav")
    context = make_context(
        input_data={"input_type": "audio"},
        audio_input=audio,
        chat_history=[{"role": "user", "content": ""}],
        **_fake_creds(mocker),
    )
    node = _agent("deepseek-chat", provider="deepseek")
    # Act / Assert
    with pytest.raises(ValueError, match="does not accept audio"):
        await node.execute(node_input({"input_type": "audio"}, context))


async def test_audio_input_mode_text_ignores_audio(mock_llm, mocker) -> None:
    # Arrange: audioInput="text" must never send audio, even on an audio-capable model.
    mock_llm.set_response("hi there")
    audio = AudioInput(bytes=b"RIFFwav", mime="audio/wav", filename="voice.wav")
    context = make_context(
        input_data={"input_type": "audio"},
        audio_input=audio,
        chat_history=[{"role": "user", "content": "typed text"}],
        **_fake_creds(mocker),
    )
    node = _agent("gemini-3-flash-preview", audio_input="text")
    # Act
    await node.execute(node_input({"input_type": "audio"}, context))
    # Assert
    messages = mock_llm.calls[0]["messages"]
    parts = _content_parts(messages)
    assert not any(p.get("type") in {"input_audio", "audio", "file"} for p in parts)


async def test_audio_input_mode_audio_requires_audio_turn(mocker) -> None:
    # Arrange: audioInput="audio" with no audio present must raise, not silently use text.
    context = make_context(
        input_data={"input_type": "text"},
        audio_input=None,
        chat_history=[{"role": "user", "content": "typed text"}],
        **_fake_creds(mocker),
    )
    node = _agent("gemini-3-flash-preview", audio_input="audio")
    # Act / Assert
    with pytest.raises(ValueError, match="[Aa]udio"):
        await node.execute(node_input({"input_type": "text"}, context))


async def test_audio_input_mode_auto_after_transcribe_uses_text(mock_llm, mocker) -> None:
    # Arrange: transcribe upstream flips input_type to "text" even though context.audio_input
    # is still set (same run) — the audio branch must be branch-local, not context-global.
    mock_llm.set_response("hi there")
    audio = AudioInput(bytes=b"RIFFwav", mime="audio/wav", filename="voice.wav")
    context = make_context(
        input_data={"input_type": "text"},
        audio_input=audio,
        chat_history=[{"role": "user", "content": "transcribed text"}],
        **_fake_creds(mocker),
    )
    node = _agent("gemini-3-flash-preview")  # default "auto"
    # Act
    await node.execute(node_input({"input_type": "text"}, context))
    # Assert
    messages = mock_llm.calls[0]["messages"]
    parts = _content_parts(messages)
    assert not any(p.get("type") in {"input_audio", "audio", "file"} for p in parts)


async def test_audio_turn_with_unsupported_mime_raises(mocker) -> None:
    # Arrange: an audio-capable model, but a mime pydantic_ai's BinaryContent
    # does not recognize (e.g. a browser MediaRecorder default).
    audio = AudioInput(bytes=b"\x1aE\xdf\xa3", mime="audio/webm", filename="voice.webm")
    context = make_context(
        input_data={"input_type": "audio"},
        audio_input=audio,
        chat_history=[{"role": "user", "content": ""}],
        **_fake_creds(mocker),
    )
    node = _agent("gemini-3-flash-preview")
    # Act / Assert
    with pytest.raises(ValueError, match="not supported"):
        await node.execute(node_input({"input_type": "audio"}, context))
