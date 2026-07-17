"""Voice gate: load an inbound audio blob onto the run's execution context.

Called by the ``/execute/audio`` endpoints before dispatch. It reads the START
node's voice config, enforces the accept-voice flag and the size cap, and
returns the raw bytes as an ``AudioInput`` for the caller to attach to the
execution context — transcription is NO LONGER done here, it is an explicit
``transcribe`` node.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.workflow import Workflow
from assemblix_api.execution.graph_navigator import GraphNavigator
from assemblix_api.schemas.execution import AudioInput
from assemblix_api.schemas.node import StartNodeConfig


def ensure_audio_run_is_synchronous(*, input_data: dict, queued: bool) -> None:
    """Audio bytes live in memory for one run; a queued run would lose them."""
    if queued and input_data.get("input_type") == "audio":
        raise ValueError("Audio input is only supported on synchronous runs")


async def load_audio_into_input_data(
    *,
    workflow: Workflow,
    input_data: dict,
    file: UploadFile,
) -> AudioInput:
    """Validate + load the inbound audio blob into the run.

    Sets ``input_data["message"] = ""`` and ``input_data["input_type"] = "audio"``,
    and returns the bytes as an ``AudioInput`` for the caller to attach to the
    execution context. Transcription is NO LONGER done here — it is an explicit
    ``transcribe`` node.

    Raises:
        HTTPException(400): the START node does not accept voice.
        HTTPException(413): the audio exceeds ``voice_max_upload_bytes``.
    """
    start_id = GraphNavigator.find_start_node(workflow.nodes)
    start_node = next((n for n in workflow.nodes if n["id"] == start_id), None)
    start_cfg = StartNodeConfig(**((start_node or {}).get("config") or {}))
    if not start_cfg.accept_voice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This workflow does not accept voice input",
        )

    max_bytes = get_settings().voice_max_upload_bytes
    audio_bytes = await file.read(max_bytes + 1)
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file is too large",
        )

    filename = file.filename or "voice.wav"
    mime = getattr(file, "content_type", None) or "audio/wav"

    input_data["message"] = ""
    input_data["input_type"] = "audio"
    # Metadata marker only (no bytes — those stay on context.audio_input) so
    # CEL/authors can see `input.audio` on audio runs.
    input_data["audio"] = {"filename": filename, "mime": mime}
    return AudioInput(bytes=audio_bytes, mime=mime, filename=filename)
