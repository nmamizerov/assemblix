from decimal import Decimal

from assemblix_api.execution.cost_accumulator import accumulate_step_cost

from ..nodes._helpers import make_context


def test_voice_system_cost_routes_to_voice_bucket() -> None:
    """A voice cost with used_system_key goes to system_voice_cost_usd."""
    # Arrange
    context = make_context()
    metadata = {"cost": 0.003, "used_system_key": True, "cost_kind": "voice"}
    # Act
    updated = accumulate_step_cost(context, metadata)
    # Assert
    assert updated.system_voice_cost_usd == Decimal("0.003")
    assert updated.system_key_cost_usd == Decimal("0")


def test_voice_own_cost_routes_to_own_voice_bucket() -> None:
    """A voice cost on an own key goes to own_voice_cost_usd (not charged later)."""
    # Arrange
    context = make_context()
    metadata = {"cost": 0.003, "used_system_key": False, "cost_kind": "voice"}
    # Act
    updated = accumulate_step_cost(context, metadata)
    # Assert
    assert updated.own_voice_cost_usd == Decimal("0.003")


def test_llm_cost_still_routes_to_llm_bucket() -> None:
    """Non-voice cost keeps the existing LLM routing."""
    # Arrange
    context = make_context()
    metadata = {"cost": 0.01, "used_system_key": True}
    # Act
    updated = accumulate_step_cost(context, metadata)
    # Assert
    assert updated.system_key_cost_usd == Decimal("0.01")
    assert updated.system_voice_cost_usd == Decimal("0")


def test_voiced_agent_step_accumulates_both_llm_and_voice() -> None:
    """A voiced agent step carries LLM `cost` AND `voice_cost`; both buckets fill."""
    # Arrange
    context = make_context()
    metadata = {
        "cost": 0.01,
        "used_system_key": True,
        "voice_cost": 0.003,
        "voice_used_system_key": True,
    }
    # Act
    updated = accumulate_step_cost(context, metadata)
    # Assert
    assert updated.system_key_cost_usd == Decimal("0.01")
    assert updated.system_voice_cost_usd == Decimal("0.003")
