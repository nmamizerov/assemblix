# /execution/cost_accumulator.py
"""Centralized accumulation of LLM call cost in ExecutionContext.

Previously the agent node itself mutated the billing state of the context, and the
executor overwrote it from metadata. Now the node emits only per-step facts
(`cost` + `used_system_key`), and the accumulation happens here, additively and in
one place (safe under Phase 3 retries). There is no credit logic here — only raw USD.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from assemblix_api.schemas.execution import ExecutionContext


def accumulate_step_cost(
    context: ExecutionContext,
    metadata: dict | None,
) -> ExecutionContext:
    """Add the step cost to the right bucket (system / own) and return a new context."""
    if not metadata:
        return context

    # Voice cost is emitted under dedicated keys (a voiced agent step ALSO carries its own
    # LLM `cost`), so add it separately to the voice bucket before the LLM cost below.
    voice_cost = Decimal(str(metadata.get("voice_cost", 0) or 0))
    if voice_cost > 0:
        if metadata.get("voice_used_system_key", False):
            context = replace(
                context, system_voice_cost_usd=context.system_voice_cost_usd + voice_cost
            )
        else:
            context = replace(context, own_voice_cost_usd=context.own_voice_cost_usd + voice_cost)

    step_cost = Decimal(str(metadata.get("cost", 0) or 0))
    if step_cost == 0:
        return context

    is_system = metadata.get("used_system_key", False)
    if metadata.get("cost_kind") == "voice":
        if is_system:
            return replace(context, system_voice_cost_usd=context.system_voice_cost_usd + step_cost)
        return replace(context, own_voice_cost_usd=context.own_voice_cost_usd + step_cost)

    if is_system:
        return replace(context, system_key_cost_usd=context.system_key_cost_usd + step_cost)
    return replace(context, own_key_cost_usd=context.own_key_cost_usd + step_cost)
