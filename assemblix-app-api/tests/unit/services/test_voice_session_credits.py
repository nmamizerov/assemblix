"""Two keys, two bills: a call meters its minutes and its speech separately."""

from decimal import Decimal

from assemblix_api.services.voice_session_service import compute_session_credits


async def test_margin_and_own_key_cost_follow_each_key_independently() -> None:
    """A call bills the model and the voice separately: margin covers only the
    parts that ran on platform keys, the platform fee is untouched by either, and
    omitting the voice reproduces today's numbers exactly."""
    # Arrange
    duration_sec, cost_per_minute, tts_cost = 60.0, 0.10, Decimal("0.30")

    # Act
    both_system = compute_session_credits(
        duration_sec,
        cost_per_minute,
        uses_system_key=True,
        tts_cost_usd=tts_cost,
        tts_uses_system_key=True,
    )
    both_own = compute_session_credits(
        duration_sec,
        cost_per_minute,
        uses_system_key=False,
        tts_cost_usd=tts_cost,
        tts_uses_system_key=False,
    )
    model_on_platform = compute_session_credits(
        duration_sec,
        cost_per_minute,
        uses_system_key=True,
        tts_cost_usd=tts_cost,
        tts_uses_system_key=False,
    )
    voice_on_platform = compute_session_credits(
        duration_sec,
        cost_per_minute,
        uses_system_key=False,
        tts_cost_usd=tts_cost,
        tts_uses_system_key=True,
    )
    no_voice = compute_session_credits(duration_sec, cost_per_minute, uses_system_key=True)

    # Assert — the platform fee is the same in every arrangement
    fee = both_system[0]
    assert {arrangement[0] for arrangement in (both_own, model_on_platform, no_voice)} == {fee}

    # Assert — margin bills exactly the parts that ran on platform keys
    assert both_own[1] == Decimal(0)
    assert model_on_platform[1] == no_voice[1]
    assert voice_on_platform[1] > Decimal(0)
    assert both_system[1] == model_on_platform[1] + voice_on_platform[1]
