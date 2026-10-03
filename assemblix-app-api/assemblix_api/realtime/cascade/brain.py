"""The text brain of a cascade call: user text in, streamed reply text out."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol

from assemblix_api.execution.agent_runner import AgentRunner
from assemblix_api.external.llm.base import TokenUsage
from assemblix_api.external.llm.litellm_model import build_litellm_model
from assemblix_api.external.llm.pricing import compute_cost

_CHARS_PER_TOKEN = 4

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
    cached_input_tokens: int = 0
    effective_model: str | None = None


class Brain(Protocol):
    async def prepare(self, *, instructions: str) -> None: ...

    def describe(self) -> dict[str, Any]:
        """Provider, model and params the brain calls the LLM with."""
        ...

    def conversation(self, history: Sequence[Turn], user_text: str) -> list[dict[str, str]]:
        """The messages a reply to ``user_text`` sends, system instructions excluded."""
        ...

    async def reply(
        self, *, history: Sequence[Turn], user_text: str, on_delta: OnDelta
    ) -> BrainUsage: ...

    def estimate_usage(self, messages: list[dict[str, str]], response: str) -> BrainUsage:
        """Approximate spend of a call cancelled before the provider reported usage."""
        ...


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

    def describe(self) -> dict[str, Any]:
        return {"provider": self._provider, "model": self._model_name, "params": self._params}

    def conversation(self, history: Sequence[Turn], user_text: str) -> list[dict[str, str]]:
        recent = [turn for turn in history if turn.text][-self._history_turns :]
        messages = [{"role": turn.role, "content": turn.text} for turn in recent]
        messages.append({"role": "user", "content": user_text})
        return messages

    async def reply(
        self, *, history: Sequence[Turn], user_text: str, on_delta: OnDelta
    ) -> BrainUsage:
        result = await self._runner.run(
            model=self._model,
            provider=self._provider,
            model_name=self._model_name,
            instructions=self._instructions,
            conversation=self.conversation(history, user_text),
            on_delta=on_delta,
        )
        meta = result.metadata
        return BrainUsage(
            input_tokens=int(meta.get("input_tokens") or 0),
            output_tokens=int(meta.get("output_tokens") or 0),
            cost_usd=Decimal(str(meta.get("cost") or 0)),
            cached_input_tokens=int(meta.get("cached_input_tokens") or 0),
            effective_model=meta.get("effective_model"),
        )

    def estimate_usage(self, messages: list[dict[str, str]], response: str) -> BrainUsage:
        prompt_chars = len(self._instructions) + sum(len(m["content"]) for m in messages)
        tokens = TokenUsage(
            input_tokens=prompt_chars // _CHARS_PER_TOKEN,
            output_tokens=len(response) // _CHARS_PER_TOKEN,
        )
        cost = compute_cost(self._provider, self._model_name, tokens)
        return BrainUsage(
            input_tokens=tokens.input_tokens,
            output_tokens=tokens.output_tokens,
            cost_usd=Decimal(str(cost)),
        )
