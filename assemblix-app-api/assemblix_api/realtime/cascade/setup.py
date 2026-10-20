"""What a cascade call is built from, and what it spent."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from assemblix_api.schemas.voice_agent import TurnConfig


@dataclass(frozen=True)
class CascadeSetup:
    stt_provider: str
    stt_model: str
    stt_api_key: str
    stt_uses_system_key: bool
    stt_cost_per_minute: float
    turn: TurnConfig
    brain_provider: str
    brain_model: str
    brain_api_key: str
    brain_uses_system_key: bool
    brain_params: dict[str, Any]
    history_turns: int


@dataclass
class CascadeMeter:
    stt_seconds: float = 0.0
    brain_cost_usd: Decimal = Decimal(0)


def cascade_spend(setup: CascadeSetup, meter: CascadeMeter) -> list[tuple[Decimal, bool]]:
    """(USD spent, on a system key) per cascade stage; TTS is metered separately."""
    stt = Decimal(str(meter.stt_seconds)) / Decimal(60) * Decimal(str(setup.stt_cost_per_minute))
    return [(stt, setup.stt_uses_system_key), (meter.brain_cost_usd, setup.brain_uses_system_key)]


def call_details(
    setup: CascadeSetup,
    meter: CascadeMeter,
    *,
    instructions: str,
    tts_provider: str | None,
    tts_model: str | None,
    tts_chars: int,
    tts_cost_usd: Decimal,
) -> dict[str, Any]:
    """What a cascade call ran with and spent per stage, stored once per call."""
    stt_cost, llm_cost = (spend for spend, _ in cascade_spend(setup, meter))
    return {
        "instructions": instructions,
        "stt": {"provider": setup.stt_provider, "model": setup.stt_model},
        "brain": {
            "provider": setup.brain_provider,
            "model": setup.brain_model,
            "params": setup.brain_params,
            "historyTurns": setup.history_turns,
        },
        "tts": {"provider": tts_provider, "model": tts_model},
        "costs": {
            "sttSeconds": round(meter.stt_seconds, 3),
            "sttCostUsd": float(stt_cost),
            "llmCostUsd": float(llm_cost),
            "ttsChars": tts_chars,
            "ttsCostUsd": float(tts_cost_usd),
        },
    }
