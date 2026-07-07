from assemblix_api.schemas.debug_events import (
    AlignmentData,
    AudioDeltaEventData,
    DebugEventType,
)


def test_audio_delta_event_data_serializes_camelcase():
    # Arrange
    data = AudioDeltaEventData(
        node_id="agent-1",
        step_number=3,
        audio="QUJD",
        alignment=AlignmentData(
            chars=["H", "i"], char_start_times_ms=[0, 40], char_durations_ms=[40, 60]
        ),
    )
    # Act
    dumped = data.model_dump(by_alias=True)
    # Assert
    assert dumped["nodeId"] == "agent-1"
    assert dumped["stepNumber"] == 3
    assert dumped["format"] == "pcm_16000"
    assert dumped["alignment"]["charStartTimesMs"] == [0, 40]


def test_audio_delta_allows_no_alignment():
    # Arrange / Act
    data = AudioDeltaEventData(node_id="a", step_number=1, audio="QQ==")
    # Assert
    assert data.alignment is None
    assert DebugEventType.AUDIO_DELTA.value == "audio_delta"
