"""Transcribe node — normalize an audio turn to text where the user places it.

Audio input -> transcript (via ``external/voice/transcription.py::transcribe``).
Text input -> passthrough (no-op). With ``saveAsUserMessage`` (default true) the
transcript is recorded as the user turn in chat history.
"""

from __future__ import annotations

from uuid import UUID

from assemblix_api.core.node_registry import register_node
from assemblix_api.enums import MessageRole
from assemblix_api.external.voice.transcription import transcribe
from assemblix_api.schemas import BaseNode, NodeInput, NodeOutput
from assemblix_api.schemas.node import TranscribeNodeConfig
from assemblix_api.schemas.node_descriptor import NodeDescriptor, NodeProperty


@register_node("transcribe")
class TranscribeNode(BaseNode):
    def __init__(self, node_config: dict) -> None:
        super().__init__(node_config)
        self.typed_config = TranscribeNodeConfig(**node_config["config"])

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        data = dict(node_input.data)
        context = node_input.context
        if data.get("input_type") != "audio" or context.audio_input is None:
            return NodeOutput(data=data)  # passthrough (already text)

        cfg = self.typed_config.voice_model
        assert cfg is not None
        api_key = ""
        if context.credential_service is not None:
            api_key, _ = await context.credential_service.get_voice_api_key_with_fallback(
                credentials_id=UUID(cfg.credential_id) if cfg.credential_id else None,
                project_id=context.project_id,
                voice_provider=cfg.provider,
                organization_plan=context.organization_plan,
            )
        result = await transcribe(
            audio_bytes=context.audio_input.bytes,
            filename=context.audio_input.filename,
            provider=cfg.provider,
            model=cfg.model,
            api_key=api_key,
        )
        data["message"] = result.text
        data["input_type"] = "text"

        if self.typed_config.save_as_user_message and context.chat_session_id:
            assert context.chat_message_service is not None
            await context.chat_message_service.save_message(
                chat_session_id=context.chat_session_id,
                role=MessageRole.USER,
                content=result.text,
            )
        return NodeOutput(data=data)

    @classmethod
    def descriptor(cls) -> NodeDescriptor:
        return NodeDescriptor(
            type="transcribe",
            display_name="Transcribe",
            description="Turn an audio turn into text (passthrough if already text).",
            icon="AudioLines",
            properties=[
                NodeProperty(
                    name="saveAsUserMessage",
                    display_name="Save as user message",
                    type="boolean",
                    default=True,
                ),
            ],
        )
