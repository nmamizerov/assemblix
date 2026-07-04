"""Unified LLM call cost calculation.

Behavior:
- If the provider itself returned `native_cost > 0` (LiteLLM does this for
  OpenAI/Claude/DeepSeek) — we trust it. It is more accurate than the
  registry because it accounts for regional/contractual prices.
- Otherwise we compute from `models/<provider>.json` × tokens from usage.
- If the model/provider is unknown — we return 0.0 so as not to overcharge by
  mistake. A CI check prevents models without prices from getting into the
  registry (see tests/external/llm/test_pricing_sanity.py).
"""

from __future__ import annotations

from assemblix_api.external.llm.base import TokenUsage
from assemblix_api.external.llm.model_catalog import find_model_metadata


def compute_cost(
    provider: str,
    model: str,
    usage: TokenUsage,
    native_cost: float | None = None,
) -> float:
    if native_cost is not None and native_cost > 0:
        return native_cost

    meta = find_model_metadata(provider, model)
    if meta is None:
        return 0.0

    return (
        usage.input_tokens * meta.input_cost_per_million
        + usage.output_tokens * meta.output_cost_per_million
    ) / 1_000_000
