from assemblix_api.nodes.transcribe_node import TranscribeNode
from assemblix_api.schemas.execution import AudioInput

from ._helpers import build_node, make_context, node_input


def _node(config: dict | None = None) -> TranscribeNode:
    return build_node(TranscribeNode, "transcribe", config or {})


async def test_audio_input_is_transcribed(mocker) -> None:
    # Arrange
    mocker.patch(
        "assemblix_api.nodes.transcribe_node.transcribe",
        return_value=mocker.Mock(text="hello world"),
    )
    cred = mocker.Mock()
    cred.get_voice_api_key_with_fallback = mocker.AsyncMock(return_value=("k", False))
    audio = AudioInput(bytes=b"RIFF", mime="audio/wav", filename="voice.wav")
    context = make_context(
        input_data={"input_type": "audio"}, audio_input=audio, credential_service=cred
    )
    node = _node({"voiceModel": {"provider": "openai", "model": "whisper-1"}})
    # Act
    out = await node.execute(node_input({"input_type": "audio"}, context))
    # Assert
    assert out.data["message"] == "hello world"
    assert out.data["input_type"] == "text"


async def test_text_input_passthrough(mocker) -> None:
    # Arrange
    spy = mocker.patch("assemblix_api.nodes.transcribe_node.transcribe")
    context = make_context(input_data={"input_type": "text"})
    node = _node({"voiceModel": {"provider": "openai", "model": "whisper-1"}})
    # Act
    out = await node.execute(node_input({"message": "typed", "input_type": "text"}, context))
    # Assert
    assert out.data["message"] == "typed"
    spy.assert_not_called()


async def test_save_as_user_message_writes_user_turn(mocker) -> None:
    # Arrange
    mocker.patch(
        "assemblix_api.nodes.transcribe_node.transcribe",
        return_value=mocker.Mock(text="hello"),
    )
    save = mocker.AsyncMock()
    cred = mocker.Mock()
    cred.get_voice_api_key_with_fallback = mocker.AsyncMock(return_value=("k", False))
    audio = AudioInput(bytes=b"RIFF", mime="audio/wav", filename="voice.wav")
    from uuid import uuid4

    context = make_context(
        input_data={"input_type": "audio"},
        audio_input=audio,
        chat_session_id=uuid4(),
        credential_service=cred,
        chat_message_service=mocker.Mock(save_message=save),
    )
    node = _node(
        {
            "voiceModel": {"provider": "openai", "model": "whisper-1"},
            "saveAsUserMessage": True,
        }
    )
    # Act
    await node.execute(node_input({"input_type": "audio"}, context))
    # Assert
    save.assert_awaited_once()
