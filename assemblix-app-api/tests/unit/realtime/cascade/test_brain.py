from decimal import Decimal
from typing import Any

from assemblix_api.realtime.cascade.brain import PromptBrain, Turn
from assemblix_api.schemas.execution import AgentExecutionResult


class _Runner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> AgentExecutionResult:
        self.calls.append(kwargs)
        await kwargs["on_delta"]("Добрый ")
        await kwargs["on_delta"]("день!")
        return AgentExecutionResult(
            content="Добрый день!",
            parsed_content=None,
            metadata={"input_tokens": 120, "output_tokens": 6, "cost": 0.00002},
            messages=[],
            tool_executions=[],
        )


async def test_reply_streams_deltas_and_reports_usage() -> None:
    runner = _Runner()
    built: list[tuple] = []
    brain = PromptBrain(
        provider="gemini",
        model="gemini-2.5-flash-lite",
        api_key="k",
        params={"temperature": 0.3},
        history_turns=2,
        runner=runner,
        build_model=lambda *a, **kw: built.append((a, kw)) or "MODEL",
    )
    await brain.prepare(instructions="Ты клиент аптеки.")
    deltas: list[str] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    usage = await brain.reply(
        history=[
            Turn("user", "раз"),
            Turn("assistant", ""),
            Turn("assistant", "два"),
            Turn("user", "три"),
        ],
        user_text="четыре",
        on_delta=on_delta,
    )

    assert deltas == ["Добрый ", "день!"]
    assert usage.input_tokens == 120
    assert usage.output_tokens == 6
    assert usage.cost_usd == Decimal("0.00002")
    call = runner.calls[0]
    assert call["model"] == "MODEL"
    assert call["instructions"] == "Ты клиент аптеки."
    # Empty turns dropped, only the last `history_turns` kept, current turn last.
    assert call["conversation"] == [
        {"role": "assistant", "content": "два"},
        {"role": "user", "content": "три"},
        {"role": "user", "content": "четыре"},
    ]
    assert built == [(("gemini", "gemini-2.5-flash-lite", "k"), {"params": {"temperature": 0.3}})]
