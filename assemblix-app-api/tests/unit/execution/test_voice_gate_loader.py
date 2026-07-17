from types import SimpleNamespace
from uuid import uuid4

from assemblix_api.execution.voice_gate import load_audio_into_input_data
from assemblix_api.schemas.execution import AudioInput


class _UploadStub:
    def __init__(self, data: bytes, filename: str) -> None:
        self._data = data
        self.filename = filename

    async def read(self, n: int) -> bytes:
        return self._data


def _workflow_with_accept_voice() -> SimpleNamespace:
    start = {
        "id": "s1",
        "type": "start",
        "config": {"acceptVoice": True},
    }
    return SimpleNamespace(nodes=[start], project_id=uuid4())


async def test_loader_puts_audio_ref_and_returns_bytes(mocker) -> None:
    # Arrange
    input_data: dict = {}
    file = _UploadStub(b"RIFFwav", "voice.wav")
    workflow = _workflow_with_accept_voice()

    # Act
    audio = await load_audio_into_input_data(workflow=workflow, input_data=input_data, file=file)

    # Assert
    assert isinstance(audio, AudioInput)
    assert audio.bytes == b"RIFFwav"
    assert input_data["message"] == ""
    assert input_data["input_type"] == "audio"
    # Metadata marker only (no bytes) so CEL/authors can see `input.audio`.
    assert input_data["audio"] == {"filename": "voice.wav", "mime": "audio/wav"}
