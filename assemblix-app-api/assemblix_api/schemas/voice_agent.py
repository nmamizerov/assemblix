"""Voice agent configuration schema.

Deliberately reuses the node schemas: ``AgentInstruction`` is the same prompt
format authors already use on the agent node, and ``VoiceOutputConfig`` already
carries provider/model/voice/credential. Workflow hook references are plain
strings without a foreign key, matching how ``knowledge_base_ids`` is stored in
node configs today.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import AgentProvider
from assemblix_api.schemas.node import AgentInstruction, VoiceOutputConfig, WorkflowAvatarConfig


class SttConfig(DTOModel):
    provider: Literal["yandex"]
    # Yandex recognition model name, not a catalog id.
    model: str = "general"
    credential_id: str | None = None


class TurnConfig(DTOModel):
    min_silence_ms: int = Field(default=200, ge=64, le=2000)
    max_silence_ms: int = Field(default=1500, ge=200, le=5000)
    smart_turn: bool = True
    smart_turn_threshold: float = Field(default=0.5, gt=0, lt=1)
    preroll_ms: int = Field(default=300, ge=0, le=1000)
    # Start the reply during the pause, before end of turn is confirmed; shown only then.
    speculative: bool = True

    @model_validator(mode="after")
    def _silence_order(self) -> TurnConfig:
        if self.max_silence_ms < self.min_silence_ms:
            raise ValueError("max_silence_ms must not be below min_silence_ms")
        return self


class PromptBrainConfig(DTOModel):
    type: Literal["prompt"]
    provider: AgentProvider
    model: str
    credential_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    # Messages kept verbatim after the instructions; user and assistant count one each.
    history_turns: int = Field(default=40, ge=2, le=400)


class CascadeConfig(DTOModel):
    stt: SttConfig
    turn: TurnConfig = Field(default_factory=TurnConfig)
    brain: PromptBrainConfig


class VoiceAgentConfig(DTOModel):
    mode: Literal["realtime", "cascade"] = "realtime"
    instructions: list[AgentInstruction] = Field(min_length=1)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    first_message: str | None = None
    language: str = "ru"
    voice: VoiceOutputConfig | None = None
    # External speech synthesis. Present means the model answers in text and this
    # provider speaks it; absent means the model's own voice. The block *is* the
    # toggle, so "enabled but unconfigured" cannot be expressed.
    tts: VoiceOutputConfig | None = None
    cascade: CascadeConfig | None = None
    # A face lip-synced to whatever voice the agent speaks with. Present means the
    # call's media runs through LiveKit; absent means a plain voice call.
    avatar: WorkflowAvatarConfig | None = None
    # Free-form provider tunables (vad_silence_ms, temperature, interruptible,
    # max_session_sec). Same pattern as AgentNodeConfig.params; system ceilings
    # in Settings always win.
    params: dict[str, Any] = Field(default_factory=dict)
    turn_workflow_id: str | None = None
    final_workflow_id: str | None = None

    @model_validator(mode="after")
    def _blocks_match_mode(self) -> VoiceAgentConfig:
        if self.mode == "realtime":
            if self.voice is None:
                raise ValueError("A realtime agent needs a `voice` model")
            if self.cascade is not None:
                raise ValueError("`cascade` is only valid with mode='cascade'")
        else:
            if self.cascade is None:
                raise ValueError("A cascade agent needs a `cascade` block")
            if self.tts is None:
                raise ValueError("A cascade agent needs `tts` to speak")
        return self
