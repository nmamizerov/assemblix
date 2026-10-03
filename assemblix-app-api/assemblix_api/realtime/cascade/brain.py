"""The text brain of a cascade call: user text in, streamed reply text out."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol

from assemblix_api.execution.agent_runner import AgentRunner
from assemblix_api.external.llm.litellm_model import build_litellm_model

OnDelta = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class BrainUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)


class Brain(Protocol):
    async def prepare(self, *, instructions: str) -> None: ...

    async def reply(
        self, *, history: Sequence[Turn], user_text: str, on_delta: OnDelta
    ) -> BrainUsage: ...


class PromptBrain:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        params: dict[str, Any],
        history_turns: int,
        runner: Any = None,
        build_model: Callable[..., Any] = build_litellm_model,
    ) -> None:
        self._provider = provider
        self._model_name = model
        self._api_key = api_key
        self._params = params
        self._history_turns = history_turns
        self._runner = runner or AgentRunner()
        self._build_model = build_model
        self._model: Any = None
        self._instructions = ""

    async def prepare(self, *, instructions: str) -> None:
        self._instructions = instructions
        self._model = self._build_model(
            self._provider, self._model_name, self._api_key, params=self._params
        )

    async def reply(
        self, *, history: Sequence[Turn], user_text: str, on_delta: OnDelta
    ) -> BrainUsage:
        recent = [turn for turn in history if turn.text][-self._history_turns :]
        conversation = [{"role": turn.role, "content": turn.text} for turn in recent]
        conversation.append({"role": "user", "content": user_text})
        result = await self._runner.run(
            model=self._model,
            provider=self._provider,
            model_name=self._model_name,
            instructions=self._instructions,
            conversation=conversation,
            on_delta=on_delta,
        )
        meta = result.metadata
        return BrainUsage(
            input_tokens=int(meta.get("input_tokens") or 0),
            output_tokens=int(meta.get("output_tokens") or 0),
            cost_usd=Decimal(str(meta.get("cost") or 0)),
        )
