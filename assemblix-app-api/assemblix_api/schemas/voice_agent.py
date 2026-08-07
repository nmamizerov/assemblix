"""Voice agent configuration schema.

Deliberately reuses the node schemas: ``AgentInstruction`` is the same prompt
format authors already use on the agent node, and ``VoiceOutputConfig`` already
carries provider/model/voice/credential. Workflow hook references are plain
strings without a foreign key, matching how ``knowledge_base_ids`` is stored in
node configs today.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from assemblix_api.dto.base import DTOModel
from assemblix_api.schemas.node import AgentInstruction, VoiceOutputConfig


class VoiceAgentConfig(DTOModel):
    instructions: list[AgentInstruction] = Field(min_length=1)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    first_message: str | None = None
    language: str = "ru"
    voice: VoiceOutputConfig
    # Free-form provider tunables (vad_silence_ms, temperature, interruptible,
    # max_session_sec). Same pattern as AgentNodeConfig.params; system ceilings
    # in Settings always win.
    params: dict[str, Any] = Field(default_factory=dict)
    turn_workflow_id: str | None = None
    final_workflow_id: str | None = None
