from assemblix_api.core.settings import Settings


def test_streaming_voice_settings_have_defaults():
    # Arrange / Act
    s = Settings()
    # Assert
    assert s.stream_audio_buffer_max_chunks == 50
    assert s.voice_realtime_output_format == "pcm_16000"
    assert s.elevenlabs_ws_base_url.startswith("wss://")
    assert s.voice_realtime_chunk_schedule == [50, 120, 200, 300]
