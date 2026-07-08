from assemblix_api.external.voice.voice_catalog import has_realtime_route, list_voice_models


def test_realtime_models_are_listed():
    # Arrange / Act
    models = list_voice_models("elevenlabs", "realtime")
    # Assert
    assert any(m.id == "eleven_flash_v2_5" for m in models)
    assert all(m.capability == "realtime" for m in models)


def test_has_realtime_route():
    # Arrange / Act / Assert
    assert has_realtime_route("elevenlabs", "eleven_flash_v2_5") is True
    assert has_realtime_route("elevenlabs", "eleven_multilingual_v2") is False
    assert has_realtime_route("nope", "x") is False
