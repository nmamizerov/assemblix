# /execution/agent_runner.py
"""Running an LLM agent via Pydantic AI — a replacement for the hand-written AgentOrchestrator.

`pydantic_ai.Agent` takes care of the agent loop, tool-calling and history
management. This is a thin wrapper: build the Agent, run `run()`, map the result
into the existing `AgentExecutionResult` contract (content / parsed_content /
metadata{tokens,cost} / messages / tool_executions), so that the agent node and
result consumers change minimally.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

import structlog
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from assemblix_api.execution.exceptions import AgentRunTimeoutError
from assemblix_api.external.llm.base import TokenUsage
from assemblix_api.external.llm.pricing import compute_cost
from assemblix_api.schemas.execution import AgentExecutionResult

logger = structlog.get_logger(__name__)


def to_pydantic_messages(conversation: list[dict]) -> tuple[list[ModelMessage], str]:
    """Split the OpenAI history into (message_history, user_prompt) for Pydantic AI.

    The last message is the current user turn (placed there by the preparation phase),
    so it becomes the prompt, and everything before it is the history. If for some
    reason the last message is not a user one, the prompt stays empty and the message
    goes into the history — without raising. There are no system messages here
    (instructions are passed via the separate Agent.instructions argument).
    """
    history: list[ModelMessage] = []
    prompt = ""
    last = len(conversation) - 1

    for i, msg in enumerate(conversation):
        role = msg.get("role")
        content = msg.get("content") or ""
        if i == last and role == "user":
            prompt = content
        elif role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=content)]))

    return history, prompt


def _extract_tool_executions(messages: list[ModelMessage]) -> list[dict]:
    """Collect tool calls from Pydantic AI messages into our format."""
    calls: dict[str, dict] = {}
    order: list[str] = []

    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                calls[part.tool_call_id] = {
                    "tool_name": part.tool_name,
                    "arguments": part.args_as_dict()
                    if hasattr(part, "args_as_dict")
                    else part.args,
                    "result": None,
                    "success": True,
                    "error": None,
                    "tool_call_id": part.tool_call_id,
                }
                order.append(part.tool_call_id)
            elif isinstance(part, ToolReturnPart):
                entry = calls.get(part.tool_call_id)
                if entry is not None:
                    entry["result"] = part.content

    return [calls[cid] for cid in order]


def _make_text_delta_handler(on_delta: Callable[[str], Awaitable[None]]):
    """Build a pydantic-ai event_stream_handler that forwards ONLY assistant text.

    Fires once per model-request node (again after each tool round). The first chunk of a
    new text part arrives as PartStartEvent(TextPart) — it must not be dropped — and the rest
    as PartDeltaEvent(TextPartDelta). Tool-call / thinking events are ignored.
    """

    async def handler(ctx: object, events: object) -> None:
        async for event in events:  # type: ignore[attr-defined]
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if event.part.content:
                    await on_delta(event.part.content)
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                await on_delta(event.delta.content_delta)

    return handler


class AgentRunner:
    """Executes an agent call via Pydantic AI and maps the result."""

    async def run(
        self,
        *,
        model: Model,
        provider: str,
        model_name: str,
        instructions: str | None,
        conversation: list[dict],
        toolsets: list | None = None,
        parse_json: bool = False,
        model_settings: ModelSettings | None = None,
        total_timeout: float | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        audio: BinaryContent | None = None,
    ) -> AgentExecutionResult:
        history, prompt = to_pydantic_messages(conversation)

        # Audio turn: the current-turn `prompt` is empty text (the run carries no
        # transcript), so the audio itself becomes the user-prompt content part(s).
        run_prompt: str | list[str | BinaryContent] = prompt
        if audio is not None:
            run_prompt = [audio] if not prompt else [prompt, audio]

        agent: Agent = Agent(
            model,
            instructions=instructions,
            toolsets=toolsets or [],
        )

        # When on_delta is supplied, pydantic-ai streams text via the handler (identical
        # return contract, full tool loop). Otherwise the buffered path runs unchanged.
        event_stream_handler = _make_text_delta_handler(on_delta) if on_delta else None

        # `total_timeout` bounds the whole agent loop (many completions + tool calls), unlike
        # the per-completion litellm `timeout`. On breach we raise a FATAL AgentRunTimeoutError
        # (do NOT retry — it would re-run already-executed tools).
        run_coro = agent.run(
            run_prompt,
            message_history=history,
            model_settings=model_settings,
            event_stream_handler=event_stream_handler,
        )
        try:
            if total_timeout is not None:
                result = await asyncio.wait_for(run_coro, timeout=total_timeout)
            else:
                result = await run_coro
        except TimeoutError as exc:
            raise AgentRunTimeoutError(f"Agent run exceeded its {total_timeout}s budget") from exc

        content = result.output if isinstance(result.output, str) else str(result.output)

        parsed_content: dict | None = None
        if parse_json:
            try:
                parsed = json.loads(content)
                parsed_content = parsed if isinstance(parsed, dict) else {"value": parsed}
            except (json.JSONDecodeError, TypeError):
                parsed_content = None

        usage = result.usage
        token_usage = TokenUsage(
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            total_tokens=usage.total_tokens or 0,
        )
        cost = compute_cost(provider, model_name, token_usage)

        all_messages = result.all_messages()
        tool_executions = _extract_tool_executions(all_messages)

        # Model that actually answered (may differ from the requested one under FallbackModel).
        # Recorded for transparency; cost stays keyed on the requested (provider, model_name).
        effective_model = next(
            (
                m.model_name
                for m in reversed(all_messages)
                if isinstance(m, ModelResponse) and m.model_name
            ),
            model_name,
        )

        return AgentExecutionResult(
            content=content,
            parsed_content=parsed_content,
            metadata={
                "tokens_used": token_usage.total_tokens,
                "cost": cost,
                "tool_calls_count": len(tool_executions),
                "effective_model": effective_model,
            },
            messages=[],  # raw pydantic messages are not exposed (the contract is a list of dict)
            tool_executions=tool_executions,
        )
