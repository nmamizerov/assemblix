"""Voice gate: transcribe an inbound audio blob into the run's text input.

Called by the ``/execute/audio`` endpoints before dispatch. It reads the START
node's voice config, enforces the accept-voice flag and the size cap, resolves
the provider credential (reusing the agent-node credential chain), transcribes
the audio via the voice module, and writes the transcript into
``input_data["message"]`` — so the execution engine runs on a normal text input
and never sees audio.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, UploadFile, status

from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.workflow import Workflow
from assemblix_api.execution.graph_navigator import GraphNavigator
from assemblix_api.external.voice import transcribe
from assemblix_api.schemas.node import StartNodeConfig
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.organization_service import OrganizationService
from assemblix_api.services.project_service import ProjectService

_DEFAULT_VOICE_PROVIDER = "openai"
_DEFAULT_VOICE_MODEL = "whisper-1"


async def transcribe_into_input_data(
    *,
    workflow: Workflow,
    input_data: dict,
    file: UploadFile,
    credential_service: CredentialsService,
    organization_service: OrganizationService,
    project_service: ProjectService,
) -> None:
    """Transcribe ``file`` and set ``input_data["message"]`` in place.

    Raises:
        HTTPException(400): the workflow's START node does not accept voice.
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

    settings = get_settings()
    max_bytes = settings.voice_max_upload_bytes
    audio_bytes = await file.read(max_bytes + 1)
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file is too large",
        )

    provider = start_cfg.voice_model.provider if start_cfg.voice_model else _DEFAULT_VOICE_PROVIDER
    model = start_cfg.voice_model.model if start_cfg.voice_model else _DEFAULT_VOICE_MODEL
    credential_id = start_cfg.voice_model.credential_id if start_cfg.voice_model else None

    project = await project_service.get_by_id(workflow.project_id)
    organization = await organization_service.get_by_id(project.organization_id)
    api_key, _ = await credential_service.get_voice_api_key_with_fallback(
        credentials_id=UUID(credential_id) if credential_id else None,
        project_id=workflow.project_id,
        voice_provider=provider,
        organization_plan=organization.plan,
    )

    transcript = await transcribe(
        audio_bytes=audio_bytes,
        filename=file.filename or "audio",
        provider=provider,
        model=model,
        api_key=api_key,
    )
    input_data["message"] = transcript.text
