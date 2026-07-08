import pytest

from assemblix_api.external.voice.realtime import RealtimeTTSSession
from assemblix_api.schemas.debug_events import AlignmentData


@pytest.mark.asyncio
async def test_session_streams_audio_and_counts_chars(mock_tts_ws):
    # Arrange
    mock_tts_ws.script_audio(
        [
            (b"\x01\x02", {"chars": ["H"], "char_start_times_ms": [0], "char_durations_ms": [40]}),
            (b"\x03\x04", None),
        ]
    )
    received: list[tuple[bytes, AlignmentData | None]] = []

    async def on_audio(pcm: bytes, alignment: AlignmentData | None) -> None:
        received.append((pcm, alignment))

    session = RealtimeTTSSession(
        api_key="xi-key",
        voice_id="v1",
        model="eleven_flash_v2_5",
        on_audio=on_audio,
        connect=mock_tts_ws.connect,
    )
    # Act
    await session.open()
    await session.send_text("Hello ")
    await session.send_text("world.")
    chars = await session.flush_and_close()
    # Assert
    assert chars == len("Hello ") + len("world.")
    assert [pcm for pcm, _ in received] == [b"\x01\x02", b"\x03\x04"]
    assert received[0][1] == AlignmentData(
        chars=["H"], char_start_times_ms=[0], char_durations_ms=[40]
    )
    assert mock_tts_ws.socket.sent[0]["text"] == " "  # BOS
    assert mock_tts_ws.socket.sent[-1]["text"] == ""  # EOS
