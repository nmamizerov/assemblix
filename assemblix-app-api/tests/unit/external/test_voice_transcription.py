"""Unit tests for the voice transcription seam (external/voice/transcription.py).

The single provider seam is ``litellm.atranscription`` (for the ``transcription``
route). We patch it so no network/keys are touched and assert:

- the whisper route returns a ``Transcript`` and calls the provider with the bare
  model id (``whisper-1``, no ``openai/`` prefix);
- a model that is not in the voice registry (e.g. Gemini, not enabled yet) raises
  a clear error instead of silently failing.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from assemblix_api.external.voice.transcription import Transcript, transcribe


async def test_whisper_route_returns_transcript_with_bare_model_id(mocker: Any) -> None:
    """whisper-1 → Transcript(text/language) and the provider is called with the bare id."""
    # Arrange
    fake_response = SimpleNamespace(text="hello world", language="en", duration=1.5)
    atranscription = mocker.patch(
        "assemblix_api.external.voice.transcription.litellm.atranscription",
        return_value=fake_response,
    )

    # Act
    result = await transcribe(
        audio_bytes=b"RIFFfake-wav-bytes",
        filename="clip.webm",
        provider="openai",
        model="whisper-1",
        api_key="sk-test",
    )

    # Assert
    assert isinstance(result, Transcript)
    assert result.text == "hello world"
    assert result.language == "en"
    assert atranscription.call_count == 1
    assert atranscription.call_args.kwargs["model"] == "whisper-1"
    assert atranscription.call_args.kwargs["api_key"] == "sk-test"


async def test_unregistered_model_raises_value_error(mocker: Any) -> None:
    """A model not in the voice registry (Gemini, not enabled yet) → clear error."""
    # Arrange
    atranscription = mocker.patch(
        "assemblix_api.external.voice.transcription.litellm.atranscription",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="Unknown or unsupported voice model"):
        await transcribe(
            audio_bytes=b"audio",
            filename="clip.webm",
            provider="gemini",
            model="gemini-2.5-flash",
            api_key="sk-test",
        )
    atranscription.assert_not_called()
