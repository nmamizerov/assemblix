from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal

from pydantic import Field, TypeAdapter, WrapValidator, model_validator

if TYPE_CHECKING:
    from assemblix_api.schemas.node_descriptor import NodeDescriptor

from assemblix_api.dto.base import DTOModel
from assemblix_api.enums import AgentProvider, NodeType
from assemblix_api.schemas.execution import NodeInput, NodeOutput


class VoiceModelConfig(DTOModel):
    """Provider/model that transcribes inbound audio when a workflow accepts voice
    input on its START node. ``provider`` is a voice-provider id (e.g. "openai",
    "yandex") — intentionally not an AgentProvider, mirroring VoiceOutputConfig."""

    provider: str
    model: str
    credential_id: str | None = None


class VoiceOutputConfig(DTOModel):
    """TTS provider/voice for the agent node. ``provider`` is a voice-provider id
    (e.g. "elevenlabs"), intentionally not an AgentProvider. ``realtime`` is the
    user's explicit opt-in to live WS streaming; it only takes effect for a
    provider/model that actually has a realtime route (buffered otherwise)."""

    provider: str
    model: str
    voice_id: str | None = None
    credential_id: str | None = None
    realtime: bool = False


class WorkflowAvatarConfig(DTOModel):
    """Workflow-global avatar persona. Set in the editor header, stored in
    ``workflow.config["avatar"]``. Avatars are BYO-key only (credential_id)."""

    provider: str
    avatar_model: str
    avatar_id: str | None = None
    voice_id: str | None = None
    voice_name: str | None = None  # display-only, kept so the UI can render it
    credential_id: str | None = None


class TranscribeNodeConfig(DTOModel):
    """Config for the `transcribe` node — normalizes an audio turn to text.

    ``voice_model`` is optional so the node also works untouched on text-only runs
    (where it never reaches the transcription call anyway).
    """

    voice_model: VoiceModelConfig | None = None
    save_as_user_message: bool = True


class StartNodeConfig(DTOModel):
    # On a new session this greeting is stored as an assistant message and
    # becomes part of the chat history.
    first_phrase: str | None = None
    # Voice input: when true, the /execute/audio endpoints transcribe an inbound
    # audio blob into `input.message` before the run. `voice_model` selects the
    # transcription provider/model; it defaults to openai/whisper-1 when unset.
    accept_voice: bool = False
    voice_model: VoiceModelConfig | None = None


class AgentInstruction(DTOModel):
    role: str
    content: str


class MCPServerConfig(DTOModel):
    """MCP server connection config (backend seam; the client is not connected yet).

    The surface is ready: transport + address/command. The real connection is
    enabled in `tools/toolsets.py::_build_mcp_toolsets` with a single edit.
    """

    transport: Literal["streamable_http", "sse", "stdio"] = "streamable_http"
    url: str | None = None  # for streamable_http / sse
    command: str | None = None  # for stdio
    args: list[str] = Field(default_factory=list)  # for stdio
    env: dict[str, str] = Field(default_factory=dict)


class FallbackModelConfig(DTOModel):
    """A fallback model tried when the primary (or a previous fallback) exhausts
    transient retries (Phase 3). May point to a different provider/credential."""

    provider: AgentProvider
    model: str
    credential_id: str | None = None


class AgentNodeConfig(DTOModel):
    name: str = Field(default="Агент")
    provider: AgentProvider
    model: str
    instructions: list[AgentInstruction]
    credential_id: str | None = None  # Optional: system keys can be used instead
    # Free-form LLM parameters — temperature, max_tokens, reasoning_effort, etc.
    # Schema is provider-specific and lives in `assemblix_api/external/llm/models/<provider>.json`.
    # Legacy fields below are merged into this dict by `_merge_legacy_into_params`
    # so the executor only needs to look at one place.
    params: dict[str, Any] = Field(default_factory=dict)

    response_format: Literal["json_object", "text"] = "text"
    response_schema: dict | None = None
    # Stream this agent's free-form text output token-by-token when the run is dispatched
    # with request.stream=true. Only honored for response_format="text".
    stream: bool = False
    # Output modality (voice moved here from the END node). "text" (default) unchanged;
    # "voice" streams realtime audio when the run streams + a realtime model is set, else
    # synthesizes one buffered base64 blob at the end of the run. "avatar" reuses the
    # text streaming (2a) for a workflow-level avatar; no per-node avatar config.
    output_type: Literal["text", "voice", "avatar"] = "text"
    voice: VoiceOutputConfig | None = None
    tools: list[str] | None = None  # List of tool names, e.g. ["web_search"]
    # MCP servers (backend seam): accepted in the config, but a real client is not connected yet.
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)
    tool_choice: str | None = "auto"  # "auto", "required", "none"
    include_chat_history: bool = True  # default True for backward compatibility
    knowledge_base_ids: list[str] | None = None  # knowledge base IDs injected into the prompt

    # --- Context control ---
    # Whether this agent's answer is appended to the run's shared dialog history that
    # later agents (with include_chat_history=True) see. Default True. False makes the
    # agent "silent": its answer still flows downstream and to the final output.
    save_to_history: bool = True
    # If the answer is JSON, append only this schema field to the shared history instead
    # of the whole JSON blob. Ignored when the answer is not a dict containing this key.
    history_field: str | None = None

    # --- Reliability (Phase 3): retries / fallbacks / timeout ---
    # Fallback models tried, in order, after the primary exhausts transient retries.
    fallback_models: list[FallbackModelConfig] = Field(default_factory=list)
    # Per-node wall-clock ceiling for the whole agent loop (seconds). None → settings default.
    timeout_seconds: float | None = Field(default=None, gt=0)
    # How many times litellm retries a transient error of a single LLM call.
    # None → settings default (`llm_num_retries`). Retries are ON by default.
    max_retries: int | None = Field(default=None, ge=0, le=10)
    # Hard-timeout toggle for the last model in the chain (the last fallback, or the
    # primary when there are no fallbacks). True (default) → the per-call timeout applies
    # to it too, so no single provider can hang the run. False → the last model may run
    # up to the whole-loop budget (`timeout_seconds`), which still bounds it hard.
    enforce_timeout_on_last: bool = True

    @model_validator(mode="after")
    def _merge_legacy_into_params(self) -> "AgentNodeConfig":
        # If params already has response_format, an explicit value wins and the
        # legacy field is ignored; otherwise copy the legacy field so the canonical
        # key always lives in params.
        if "response_format" not in self.params:
            self.params["response_format"] = self.response_format
        return self


class Condition(DTOModel):
    expression: str
    name: str | None = None


class ConditionNodeConfig(DTOModel):
    conditions: list[Condition]


class UpdateVariable(DTOModel):
    variable_name: str
    value: str | dict | list | int | float | bool


class SmartMerge(DTOModel):
    """Smart merge of an object into the state."""

    source: str  # CEL expression, e.g. "input.parsed_message"
    target: Literal["state", "project"] = "state"
    target_key: str | None = None  # key in the state (e.g. "inventory"); None = whole state
    operation: Literal["add", "subtract", "overwrite"] = "overwrite"


class SetVariableNodeConfig(DTOModel):
    updates: list[UpdateVariable] = []
    merges: list[SmartMerge] = []


class EndNodeConfig(DTOModel):
    name: str = ""

    # Output source. None / "last_agent" = last agent node (default);
    # "specific_agent" = a specific agent node by ID; "custom" = fixed message.
    output_mode: Literal["last_agent", "specific_agent", "custom"] | None = None
    source_node_id: str | None = None  # for specific_agent
    custom_message: str | None = None  # for custom (CEL supported)

    # State filtering: "all" = all variables (default), "none" = return nothing,
    # "selected" = only the listed variables.
    state_filter: Literal["all", "none", "selected"] = "all"
    state_variables: list[str] = []  # variables for "selected"

    project_filter: Literal["all", "none", "selected"] = "all"
    project_variables: list[str] = []  # variables for "selected"

    # Voice output moved to the AGENT node (phase 2b). END is text-only: it selects the
    # source output (which may already carry `audio` from a voiced agent) and passes it through.

    is_error: bool = False  # business error (not a technical one)

    is_session_end: bool = False


class StickerNodeConfig(DTOModel):
    text: str


class HTTPRequestNodeConfig(DTOModel):
    url: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    headers: dict[str, str] = {}
    body: str | None = None
    query_params: dict[str, str] = {}
    timeout: int = 30
    # How many times to retry transient failures (timeouts, 429, 5xx) via tenacity.
    # None → settings default (`http_node_num_retries`). Retries are ON by default.
    max_retries: int | None = Field(default=None, ge=0, le=10)


class BaseNodeSchema(DTOModel):
    id: str
    position: dict


class StartNode(BaseNodeSchema):
    type: Literal[NodeType.START]
    config: StartNodeConfig


class AgentNode(BaseNodeSchema):
    type: Literal[NodeType.AGENT]
    config: AgentNodeConfig


class ConditionNode(BaseNodeSchema):
    type: Literal[NodeType.CONDITION]
    config: ConditionNodeConfig


class SetVariableNode(BaseNodeSchema):
    type: Literal[NodeType.SET_VARIABLE]
    config: SetVariableNodeConfig


class EndNode(BaseNodeSchema):
    type: Literal[NodeType.END]
    config: EndNodeConfig


class StickerNode(BaseNodeSchema):
    type: Literal[NodeType.STICKER]
    config: StickerNodeConfig


class PlaceholderNode(BaseNodeSchema):
    type: Literal[NodeType.PLACEHOLDER]


class HTTPRequestNode(BaseNodeSchema):
    type: Literal[NodeType.HTTP_REQUEST]
    config: HTTPRequestNodeConfig


class GenericNode(BaseNodeSchema):
    """Fallback schema for plugin / unknown node types. Config validated by the
    node's own Pydantic config at execution time, not here."""

    type: str
    config: dict[str, Any] = Field(default_factory=dict)


# Strict discriminated union for all known built-in node types.
_BuiltinNode = Annotated[
    StartNode
    | AgentNode
    | ConditionNode
    | SetVariableNode
    | EndNode
    | StickerNode
    | PlaceholderNode
    | HTTPRequestNode,
    Field(discriminator="type"),
]
_builtin_adapter: TypeAdapter[_BuiltinNode] = TypeAdapter(_BuiltinNode)

# Set of type strings owned by the built-in union above, derived from the enum so
# it stays in sync automatically. The fallback to GenericNode is ONLY for types NOT
# in this set (plugin / unknown types). A known built-in with a malformed config
# must still raise ValidationError so callers get an early, clear failure.
_BUILTIN_NODE_TYPES: frozenset[str] = frozenset(t.value for t in NodeType)


def _parse_node(value: Any, handler: Any) -> Any:
    """Route validation based on whether the node type is a known built-in.

    - Already-instantiated GenericNode: passed through as-is (response re-validation
      round-trip must not raise).
    - Unknown / plugin type (not in _BUILTIN_NODE_TYPES): accepted as GenericNode.
    - Known built-in type: always validated strictly via _builtin_adapter so that a
      malformed config (e.g. http_request missing required url) raises ValidationError
      instead of silently falling through to GenericNode.
    - Non-dict input: passed to _builtin_adapter as-is (will raise if invalid).
    """
    # Fallback applies only to unregistered/plugin types. A dict whose "type"
    # is a known built-in (or any non-dict input) goes through strict
    # validation so a malformed built-in config still errors.
    if isinstance(value, GenericNode):
        return value
    if isinstance(value, dict) and value.get("type") not in _BUILTIN_NODE_TYPES:
        # Unknown / plugin type — accept it as a GenericNode.
        return GenericNode.model_validate(value)
    # Known built-in (or non-dict): validate strictly; config errors propagate.
    return _builtin_adapter.validate_python(value)


# Permissive Node type: built-ins validate strictly, unknown types become GenericNode.
Node = Annotated[_BuiltinNode | GenericNode, WrapValidator(_parse_node)]


class BaseNode(ABC):
    # --- Capability hooks (replace the executor's hardcoded type checks) ---
    # Where this node reads its input from: the workflow's input_data (START)
    # or the previous node's output (everything else).
    input_source: ClassVar[Literal["workflow_input", "previous_output"]] = "previous_output"
    # Whether reaching this node terminates the workflow (END).
    is_terminal: ClassVar[bool] = False

    def __init__(self, node_config: dict):
        """Initialize base node with config."""
        self.node_config = node_config
        self.node_id = node_config.get("id")
        self.node_type = node_config.get("type")

    @abstractmethod
    async def execute(self, node_input: NodeInput) -> NodeOutput:
        pass

    def validate_config(self) -> list[str]:
        return []

    def get_branch_index(self, node_output: NodeOutput) -> int | None:
        """Outgoing edge index for branching nodes (CONDITION). None = single edge."""
        return None

    @classmethod
    def descriptor(cls) -> "NodeDescriptor | None":
        """Declarative spec used by GET /api/nodes and the frontend renderer.

        Return None to hide the node from the catalog (e.g. START/PLACEHOLDER).
        """
        return None
