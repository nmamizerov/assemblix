"""Unit tests for the AUDIO_DELTA `avatar` flag — the client uses it to route a PCM
chunk into the avatar's audio-passthrough stream instead of the local Web Audio player."""

from uuid import uuid4

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.debug_events import AudioDeltaEventData, DebugEventType


def test_audio_delta_data_has_avatar_default_false() -> None:
    """AudioDeltaEventData.avatar defaults to False for plain realtime-voice chunks."""
    # Arrange / Act
    data = AudioDeltaEventData(node_id="n1", step_number=1, audio="AAAA")

    # Assert
    assert data.avatar is False


async def test_emit_audio_delta_sets_avatar_flag() -> None:
    """emit_audio_delta(avatar=True) tags the live AUDIO_DELTA event's data."""
    # Arrange
    mgr = DebugEventManager()
    execution_id = uuid4()
    queue = mgr.create_stream(execution_id)

    # Act
    await mgr.emit_audio_delta(
        execution_id, step_number=1, node_id="n1", audio="AAAA", avatar=True
    )
    event = await queue.get()

    # Assert
    assert event.event_type == DebugEventType.AUDIO_DELTA
    assert event.data["avatar"] is True
