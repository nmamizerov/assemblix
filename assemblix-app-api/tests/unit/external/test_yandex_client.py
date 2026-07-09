import io

import httpx
import pytest

from assemblix_api.external.voice import yandex


def test_split_credential_parses_folder_and_key() -> None:
    # Arrange / Act
    folder, key = yandex.split_credential("b1gfolder:AQVN-secret")
    # Assert
    assert folder == "b1gfolder"
    assert key == "AQVN-secret"


def test_split_credential_keeps_colons_in_key() -> None:
    # Arrange / Act — only the first ":" separates folder id from the key.
    folder, key = yandex.split_credential("b1gfolder:a:b:c")
    # Assert
    assert folder == "b1gfolder"
    assert key == "a:b:c"


@pytest.mark.parametrize("bad", ["", "no-separator", ":onlykey", "onlyfolder:"])
def test_split_credential_rejects_malformed(bad: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        yandex.split_credential(bad)


def test_list_voices_returns_catalog() -> None:
    # Arrange / Act
    voices = yandex.list_voices()
    # Assert
    assert any(v.id == "alena" for v in voices)


async def test_synthesize_posts_with_api_key_and_folder(mocker) -> None:
    """synthesize sends Api-Key auth + folderId + voice and returns audio bytes."""
    # Arrange
    audio = b"\x00\x01"
    mock_resp = httpx.Response(200, content=audio, request=httpx.Request("POST", "http://x"))
    post = mocker.patch.object(httpx.AsyncClient, "post", return_value=mock_resp)
    # Act
    result = await yandex.synthesize(credential="b1gfolder:key", voice="alena", text="привет")
    # Assert
    assert result == audio
    assert "tts:synthesize" in post.call_args.args[0]
    assert post.call_args.kwargs["headers"]["Authorization"] == "Api-Key key"
    data = post.call_args.kwargs["data"]
    assert data["folderId"] == "b1gfolder"
    assert data["voice"] == "alena"
    assert data["text"] == "привет"


def _wav_bytes(seconds: float = 0.1, rate: int = 8000) -> bytes:
    """A tiny mono s16 WAV blob av can demux (stand-in for a browser recording)."""
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def test_to_lpcm16k_decodes_and_resamples() -> None:
    # Arrange
    wav = _wav_bytes(seconds=0.1, rate=8000)
    # Act — 0.1 s of 16 kHz mono s16 ≈ 1600 samples * 2 bytes.
    pcm = yandex._to_lpcm16k(wav)
    # Assert
    assert len(pcm) > 0
    assert len(pcm) == pytest.approx(1600 * 2, rel=0.2)


def test_to_lpcm16k_rejects_undecodable() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        yandex._to_lpcm16k(b"not audio")


async def test_transcribe_sends_lpcm_and_returns_text(mocker) -> None:
    """transcribe transcodes to LPCM, posts to stt:recognize, returns the text."""
    # Arrange
    mocker.patch.object(yandex, "_to_lpcm16k", return_value=b"PCMDATA")
    mock_resp = httpx.Response(
        200, json={"result": "распознанный текст"}, request=httpx.Request("POST", "http://x")
    )
    post = mocker.patch.object(httpx.AsyncClient, "post", return_value=mock_resp)
    # Act
    text = await yandex.transcribe(credential="b1gfolder:key", audio_bytes=b"AUDIO")
    # Assert
    assert text == "распознанный текст"
    assert "stt:recognize" in post.call_args.args[0]
    assert post.call_args.kwargs["params"]["folderId"] == "b1gfolder"
    assert post.call_args.kwargs["params"]["format"] == "lpcm"
    assert post.call_args.kwargs["content"] == b"PCMDATA"


async def test_synthesis_dispatch_routes_to_yandex(mocker) -> None:
    """A speech-capability yandex model routes to the Yandex client."""
    # Arrange
    from assemblix_api.external.voice.synthesis import SynthesisResult, synthesize

    mocker.patch(
        "assemblix_api.external.voice.synthesis.yandex.synthesize",
        return_value=b"AUDIO",
    )
    # Act
    result = await synthesize(
        text="hello",
        provider="yandex",
        model="yandex-tts-v1",
        voice_id="alena",
        api_key="b1gfolder:key",
    )
    # Assert
    assert isinstance(result, SynthesisResult)
    assert result.audio_bytes == b"AUDIO"


async def test_transcription_dispatch_routes_to_yandex(mocker) -> None:
    """A yandex transcription model routes to the Yandex recognizer, not litellm."""
    # Arrange
    from assemblix_api.external.voice.transcription import transcribe

    mocker.patch(
        "assemblix_api.external.voice.transcription.yandex.transcribe",
        return_value="привет",
    )
    # Act
    transcript = await transcribe(
        audio_bytes=b"AUDIO",
        filename="a.ogg",
        provider="yandex",
        model="general",
        api_key="b1gfolder:key",
    )
    # Assert
    assert transcript.text == "привет"
