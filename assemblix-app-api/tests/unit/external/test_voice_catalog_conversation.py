"""Voice catalog: the conversation (speech-to-speech) capability."""

from assemblix_api.external.voice.catalog import (
    VOICE_PROVIDER_LABELS,
    has_conversation_route,
    has_realtime_route,
    list_voice_models,
    list_voice_providers,
)


def test_conversation_capability_is_registered_without_disturbing_existing_ones() -> None:
    """OpenAI and Gemini expose conversation models; every prior capability is unchanged."""
    # Arrange
    speech_providers_before = list_voice_providers("speech")
    transcription_providers_before = list_voice_providers("transcription")

    # Act
    conversation_providers = list_voice_providers("conversation")
    openai_models = list_voice_models("openai", "conversation")
    gemini_models = list_voice_models("gemini", "conversation")

    # Assert — the new capability
    assert set(conversation_providers) == {"openai", "gemini"}
    assert VOICE_PROVIDER_LABELS["gemini"] == "Gemini"
    assert {m.id for m in openai_models} == {"gpt-realtime-2.1", "gpt-realtime-2.1-mini"}
    assert {m.id for m in gemini_models} == {"gemini-3.1-flash-live-preview"}
    assert all(m.capability == "conversation" and m.route == "conversation" for m in openai_models)
    assert all(m.cost_per_minute is not None for m in openai_models + gemini_models)

    # Assert — routing helper is exact, not a substring match
    assert has_conversation_route("openai", "gpt-realtime-2.1") is True
    assert has_conversation_route("gemini", "gemini-3.1-flash-live-preview") is True
    assert has_conversation_route("openai", "whisper-1") is False
    assert has_conversation_route("yandex", "yandex-tts-v3") is False
    assert has_conversation_route("nope", "gpt-realtime-2.1") is False

    # Assert — regression: existing capabilities and helpers untouched
    assert list_voice_providers("speech") == speech_providers_before
    assert list_voice_providers("transcription") == transcription_providers_before
    assert has_realtime_route("yandex", "yandex-tts-v3") is True
    assert has_realtime_route("openai", "gpt-realtime-2.1") is False
