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


def test_summary_includes_the_longest_audio_gap() -> None:
    # Arrange
    transcript = [
        {"role": "assistant", "text": "y", "timings": {"totalMs": 900, "ttsGapMaxMs": gap}}
        for gap in (0, 300, 1800)
    ]

    # Act
    summary = summarize_timings(transcript)

    # Assert
    assert summary is not None
    assert summary["ttsGapMaxMs"] == {"p50": 300, "p95": 1800}
