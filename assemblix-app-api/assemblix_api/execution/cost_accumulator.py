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

    step_cost = Decimal(str(metadata.get("cost", 0) or 0))
    if step_cost == 0:
        return context

    if metadata.get("used_system_key", False):
        return replace(context, system_key_cost_usd=context.system_key_cost_usd + step_cost)
    return replace(context, own_key_cost_usd=context.own_key_cost_usd + step_cost)
