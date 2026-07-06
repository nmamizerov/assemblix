import httpx

from assemblix_api.external.voice import elevenlabs


async def test_list_voices_parses_response(mocker) -> None:
    """list_voices maps the ElevenLabs payload to ElevenLabsVoice items."""
    # Arrange
    payload = {"voices": [{"voice_id": "v1", "name": "Rachel", "preview_url": "http://x/a.mp3"}]}
    mock_resp = httpx.Response(200, json=payload, request=httpx.Request("GET", "http://x"))
    mocker.patch.object(httpx.AsyncClient, "get", return_value=mock_resp)
    # Act
    voices = await elevenlabs.list_voices("xi-key")
    # Assert
    assert voices[0].id == "v1"
    assert voices[0].name == "Rachel"


async def test_synthesize_posts_to_voice_and_returns_bytes(mocker) -> None:
    """synthesize calls the TTS endpoint for the voice and returns audio bytes."""
    # Arrange
    audio = b"\x00\x01\x02"
    mock_resp = httpx.Response(200, content=audio, request=httpx.Request("POST", "http://x"))
    post = mocker.patch.object(httpx.AsyncClient, "post", return_value=mock_resp)
    # Act
    result = await elevenlabs.synthesize(
        api_key="xi-key", voice_id="v1", model="eleven_multilingual_v2", text="hello"
    )
    # Assert
    assert result == audio
    assert "text-to-speech/v1" in post.call_args.args[0]
    assert post.call_args.kwargs["json"]["model_id"] == "eleven_multilingual_v2"


async def test_base_url_override_routes_to_proxy(mocker, monkeypatch) -> None:
    """ELEVENLABS_API_BASE_URL override (e.g. a proxy) changes the request base URL."""
    # Arrange
    from assemblix_api.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "elevenlabs_api_base_url", "https://proxy.example/v1/")
    mock_resp = httpx.Response(200, content=b"a", request=httpx.Request("POST", "http://x"))
    post = mocker.patch.object(httpx.AsyncClient, "post", return_value=mock_resp)
    # Act
    await elevenlabs.synthesize(api_key="k", voice_id="v1", model="m", text="hi")
    # Assert — trailing slash stripped, proxy base used
    assert post.call_args.args[0] == "https://proxy.example/v1/text-to-speech/v1"
