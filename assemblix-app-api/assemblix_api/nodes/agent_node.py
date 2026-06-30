# /nodes/agent_node.py

import structlog
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel

from assemblix_api.core.concurrency_limiter import agent_call_guard
from assemblix_api.core.node_registry import register_node
from assemblix_api.core.settings import get_settings
from assemblix_api.enums import AgentProvider, NodeType, TransienceClass
from assemblix_api.execution.agent_runner import AgentRunner
from assemblix_api.execution.credential_resolver import CredentialResolver
from assemblix_api.execution.error_taxonomy import classify_error
from assemblix_api.execution.message_builder import MessageBuilder
from assemblix_api.external.llm.litellm_model import build_litellm_model
from assemblix_api.schemas import AgentNodeConfig, BaseNode
from assemblix_api.schemas.execution import ExecutionContext, NodeInput, NodeOutput
from assemblix_api.tools.registry import ToolContext
from assemblix_api.tools.toolsets import build_toolsets

logger = structlog.get_logger(__name__)


def _is_transient(exc: Exception) -> bool:
    """fallback_on predicate for FallbackModel: switch to the next model only on a
    transient error (reuses the Phase-1 taxonomy). litellm has already exhausted its own
    `num_retries` by the time the exception reaches here, so this triggers after retries."""
    return classify_error(exc) is TransienceClass.TRANSIENT


@register_node(NodeType.AGENT)
class AgentNode(BaseNode):
    """
    LLM agent node — runs on Pydantic AI.

    Responsibilities are decomposed:
    - credential resolution → CredentialResolver
    - message assembly (instructions + KB + history) → MessageBuilder
    - LLM transport (in-process litellm) → LiteLLMModel
    - tools / MCP seam → build_toolsets
    - agentic loop / tool calling → AgentRunner (pydantic_ai.Agent)

    Billing is NOT touched here: the node emits per-step facts (cost,
    used_system_key) in metadata; the executor accumulates them.
    """

    def __init__(self, node_config: dict):
        super().__init__(node_config)
        self.typed_config = AgentNodeConfig(**node_config["config"])

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        context = node_input.context
        cfg = self.typed_config
        settings = get_settings()

        # 1. Credentials for the primary model (with fallback to system keys).
        api_key, is_system_key = await self._load_credential(
            context, cfg.provider, cfg.credential_id
        )

        # 2. Combined OpenAI messages (system instructions + KB + history), then
        #    split into system instructions (text) and the conversation.
        messages = await self._build_messages(node_input)
        instructions, conversation = _split_system_messages(messages)

        # 3. Resolve response format / json parsing.
        params = dict(cfg.params)
        response_format_str = params.pop("response_format", "text")
        response_format_kwarg, parse_json = self._resolve_response_format(response_format_str)

        num_retries = cfg.max_retries if cfg.max_retries is not None else settings.llm_num_retries

        # 4. Build the primary in-process litellm model (provider quirks + sampling params).
        primary_model = build_litellm_model(
            cfg.provider.value,
            cfg.model,
            api_key,
            response_format=response_format_kwarg,
            params=params,
            num_retries=num_retries,
        )

        # 4b. Fallback models (Phase 3): build each with its own (lazily resolved) credential.
        #     FallbackModel switches over only on transient errors (after retries) via _is_transient.
        model: Model = primary_model
        if cfg.fallback_models:
            fallback_models: list[Model] = []
            for fb in cfg.fallback_models:
                fb_key, _ = await self._load_credential(context, fb.provider, fb.credential_id)
                fallback_models.append(
                    build_litellm_model(
                        fb.provider.value,
                        fb.model,
                        fb_key,
                        response_format=response_format_kwarg,
                        params=params,
                        num_retries=num_retries,
                    )
                )
            model = FallbackModel(primary_model, *fallback_models, fallback_on=_is_transient)

        # 5. Tools + MCP seam.
        toolsets = build_toolsets(cfg.tools, cfg.mcp_servers, ToolContext(settings=settings))

        # 6. Run via Pydantic AI, bounding the whole loop by the per-node wall-clock budget.
        # Release the DB connection before the (potentially minutes-long) LLM await: all
        # DB reads above (credentials, KB) are done, so commit the session and hand the
        # pooled connection back. Without this, one running workflow pins a Postgres
        # connection for its entire lifetime, capping concurrency at the pool size.
        await context.db_checkpoint()

        # Bound concurrent LLM calls per org and per provider (no-op without Redis /
        # when limits are 0): one tenant can't starve the worker pool and a burst can't
        # blow the provider's rate limit. Backpressure happens here, after the DB
        # connection is already released.
        total_timeout = cfg.timeout_seconds or settings.agent_run_timeout_seconds
        async with agent_call_guard(
            context.organization_id, cfg.provider.value, hold_timeout=total_timeout
        ):
            result = await AgentRunner().run(
                model=model,
                provider=cfg.provider.value,
                model_name=cfg.model,
                instructions=instructions or None,
                conversation=conversation,
                toolsets=toolsets,
                parse_json=parse_json,
                total_timeout=total_timeout,
            )

        return NodeOutput(
            data={
                "message": result.content,
                "parsed_message": result.parsed_content,
                "tool_executions": result.tool_executions,
            },
            metadata={
                **result.metadata,
                "model": cfg.model,
                "provider": cfg.provider.value,
                "used_system_key": is_system_key,
            },
        )

    def _resolve_response_format(self, response_format: str) -> tuple[dict | None, bool]:
        """Return (litellm response_format kwarg | None, whether to parse JSON).

        When tools are present we do not force the format on every call (as in the old
        code: the json format was applied only on the final step), but we still parse JSON.
        """
        if response_format != "json_object":
            return None, False

        parse_json = True
        if self.typed_config.tools:
            # with tools we do not force response_format on tool calls
            return None, parse_json

        if self.typed_config.response_schema:
            return {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": self.typed_config.response_schema},
            }, parse_json
        return {"type": "json_object"}, parse_json

    async def _build_messages(self, node_input: NodeInput) -> list[dict]:
        """Build messages (delegates to MessageBuilder). Kept as a public entry
        point — existing tests rely on it."""
        return await MessageBuilder().build(
            instructions=self.typed_config.instructions,
            knowledge_base_ids=self.typed_config.knowledge_base_ids,
            include_chat_history=self.typed_config.include_chat_history,
            context=node_input.context,
            node_data=node_input.data,
        )

    async def _load_credential(
        self,
        context: ExecutionContext,
        provider: AgentProvider,
        credential_id: str | None,
    ) -> tuple[str, bool]:
        """Load the API key for (provider, credential_id) via CredentialResolver.

        Returns (api_key, is_system_key). Called once per model target (primary + each
        fallback), so a fallback's credential is resolved only when its target is built.
        """
        assert context.credential_service is not None
        assert context.organization_plan is not None

        resolver = context.credential_resolver or CredentialResolver(context.credential_service)
        return await resolver.resolve(
            credential_id=credential_id,
            provider=provider,
            project_id=context.project_id,
            organization_plan=context.organization_plan,
        )

    def validate_config(self) -> list[str]:
        """Validate node configuration"""
        from assemblix_api.tools.registry import registry

        errors = []

        if not self.typed_config.instructions:
            errors.append("At least one instruction required")

        if not self.typed_config.model:
            errors.append("Model is required")

        if self.typed_config.tools:
            for tool_name in self.typed_config.tools:
                if not registry.is_registered(tool_name):
                    errors.append(f"Unknown tool: {tool_name}")

        return errors

    @classmethod
    def descriptor(cls):
        """Minimal catalog entry for the Agent node.

        The rich agent configuration form is a hand-coded custom widget on the
        frontend (registered as a custom node type), so properties stay empty here.
        """
        from assemblix_api.schemas.node_descriptor import NodeDescriptor

        return NodeDescriptor(
            type="agent",
            display_name="Agent",
            description="LLM agent node — calls a language model and runs tools.",
            category="main",
            icon="Bot",
            color="node-llm",
            properties=[],
        )


def _split_system_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Split the combined list into (system instructions as one string, dialog).

    System messages are joined into Pydantic AI instructions; the rest (user/assistant)
    go as the dialog.
    """
    system_parts: list[str] = []
    conversation: list[dict] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_parts.append(msg.get("content") or "")
        else:
            conversation.append(msg)
    return "\n\n".join(p for p in system_parts if p), conversation
