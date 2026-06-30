"""Unit tests for the DELAY node (assemblix_api/nodes/delay_node.py).

DELAY sleeps for a bounded number of seconds (clamped to 0..300) and then passes
NodeInput.data through unchanged. Tests use a 0-second delay so they stay fast, and
assert the clamping by spying on ``asyncio.sleep``.
"""

from __future__ import annotations

from assemblix_api.nodes.delay_node import DelayNode

from ._helpers import build_node, make_context, node_input


def _delay(config: dict) -> DelayNode:
    """Build a DELAY node from its config dict."""
    return build_node(DelayNode, "delay", config)  # type: ignore[return-value]


async def test_delay_passes_input_through() -> None:
    """DELAY returns NodeInput.data unchanged after sleeping."""
    # Arrange
    context = make_context(with_cel=False)
    node = _delay({"seconds": 0})
    incoming = {"message": "hi", "n": 1}

    # Act
    output = await node.execute(node_input(incoming, context))

    # Assert
    assert output.data == incoming


async def test_delay_sleeps_for_configured_seconds(mocker) -> None:
    """The configured (in-range) seconds value is passed to asyncio.sleep."""
    # Arrange
    sleep_spy = mocker.patch("assemblix_api.nodes.delay_node.asyncio.sleep")
    context = make_context(with_cel=False)
    node = _delay({"seconds": 2})

    # Act
    await node.execute(node_input({}, context))

    # Assert
    sleep_spy.assert_awaited_once_with(2.0)


async def test_delay_clamps_to_max(mocker) -> None:
    """A seconds value above the ceiling is clamped to 300."""
    # Arrange
    sleep_spy = mocker.patch("assemblix_api.nodes.delay_node.asyncio.sleep")
    context = make_context(with_cel=False)
    node = _delay({"seconds": 9999})

    # Act
    await node.execute(node_input({}, context))

    # Assert
    sleep_spy.assert_awaited_once_with(300.0)


async def test_delay_clamps_negative_to_zero(mocker) -> None:
    """A negative seconds value is clamped to 0."""
    # Arrange
    sleep_spy = mocker.patch("assemblix_api.nodes.delay_node.asyncio.sleep")
    context = make_context(with_cel=False)
    node = _delay({"seconds": -5})

    # Act
    await node.execute(node_input({}, context))

    # Assert
    sleep_spy.assert_awaited_once_with(0.0)


async def test_delay_missing_seconds_defaults_to_zero(mocker) -> None:
    """With no 'seconds' in config, DELAY sleeps for 0 seconds."""
    # Arrange
    sleep_spy = mocker.patch("assemblix_api.nodes.delay_node.asyncio.sleep")
    context = make_context(with_cel=False)
    node = _delay({})

    # Act
    await node.execute(node_input({}, context))

    # Assert
    sleep_spy.assert_awaited_once_with(0.0)
