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
