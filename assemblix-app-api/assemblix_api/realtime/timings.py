"""Per-stage latency summary of a cascade call, computed from its transcript."""

from __future__ import annotations

import math

STAGES = (
    "eouMs",
    "sttFinalMs",
    "brainFirstTokenMs",
    "ttsFirstAudioMs",
    "totalMs",
    "ttsGapMaxMs",
)


def _nearest_rank(values: list[int], percentile: int) -> int:
    index = max(0, math.ceil(percentile / 100 * len(values)) - 1)
    return values[min(index, len(values) - 1)]


def summarize_timings(transcript: list[dict]) -> dict[str, dict[str, int]] | None:
    rows = [line["timings"] for line in transcript if isinstance(line.get("timings"), dict)]
    if not rows:
        return None
    summary: dict[str, dict[str, int]] = {}
    for stage in STAGES:
        values = sorted(row[stage] for row in rows if isinstance(row.get(stage), int))
        if values:
            summary[stage] = {"p50": _nearest_rank(values, 50), "p95": _nearest_rank(values, 95)}
    return summary
