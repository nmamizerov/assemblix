from assemblix_api.realtime.timings import summarize_timings


def test_summary_is_none_without_timed_turns() -> None:
    assert summarize_timings([{"role": "user", "text": "a"}]) is None


def test_nearest_rank_percentiles_per_stage() -> None:
    transcript = [{"role": "user", "text": "x"}] + [
        {"role": "assistant", "text": "y", "timings": {"totalMs": total, "eouMs": 200}}
        for total in range(100, 2100, 100)  # 20 turns: 100..2000
    ]

    summary = summarize_timings(transcript)

    assert summary == {
        "eouMs": {"p50": 200, "p95": 200},
        "totalMs": {"p50": 1000, "p95": 1900},
    }
