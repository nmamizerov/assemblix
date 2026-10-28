"""Jev node — request building, output merge, cost metadata, descriptor (client mocked)."""

from __future__ import annotations

import pytest

from assemblix_api.core.node_registry import NodeRegistry
from assemblix_api.external.typesafe import TypeSafeError
from assemblix_api.nodes.jev_node import JevNode

from ._helpers import build_node, make_context, node_input

NOUL = {"name": "relevant", "type": "noul", "instructions": "On topic?", "trueCriteria": "yes"}
CHOICE = {
    "name": "intent",
    "type": "choice",
    "instructions": "What does the user want?",
    "options": [
        {"name": "billing", "description": "Payments"},
        {"name": "support", "description": "Help"},
    ],
}
SCORE = {"name": "urgency", "type": "score", "instructions": "How urgent?", "levels": ["a", "b", "c"]}

RESPONSE = {
    "model": "jev-1.14.0",
    "answers": {
        "relevant": {"type": "noul", "noul": 0.9},
        "intent": {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.8,
            "probabilities": {"billing": 0.9, "support": 0.1},
        },
    },
    "usage": {"input_tokens": 1_000_000, "output_tokens": 3},
}


def _node(**config) -> JevNode:
    base = {"credentialId": "00000000-0000-0000-0000-000000000001", "questions": [NOUL]}
    base.update(config)
    return build_node(JevNode, "jev", base)


@pytest.fixture
def client(mocker):
    return mocker.patch("assemblix_api.nodes.jev_node.system_one", return_value=RESPONSE)


@pytest.fixture
def context(mocker):
    cred = mocker.Mock()
    cred.get_typesafe_api_key = mocker.AsyncMock(return_value="k")
    return make_context(credential_service=cred)


async def test_builds_request_for_all_types(client, context) -> None:
    # Arrange
    node = _node(questions=[NOUL, CHOICE, SCORE])
    # Act
    await node.execute(node_input({"message": "hi"}, context))
    # Assert
    kwargs = client.await_args.kwargs
    assert kwargs["api_key"] == "k"
    assert kwargs["model"] == "jev-latest"
    assert kwargs["long_context"] is False
    assert kwargs["questions"] == {
        "relevant": {"type": "noul", "instructions": "On topic?", "criteria": {"true": "yes"}},
        "intent": {
            "type": "choice",
            "instructions": "What does the user want?",
            "criteria": {"billing": "Payments", "support": "Help"},
        },
        "urgency": {"type": "score", "instructions": "How urgent?", "criteria": ["a", "b", "c"]},
    }


async def test_noul_without_criteria_omits_them(client, context) -> None:
    # Arrange
    node = _node(questions=[{"name": "q", "type": "noul", "instructions": "x"}])
    # Act
    await node.execute(node_input({"message": "hi"}, context))
    # Assert
    assert client.await_args.kwargs["questions"] == {"q": {"type": "noul", "instructions": "x"}}


async def test_templates_rendered(client, context) -> None:
    # Arrange
    question = {"name": "q", "type": "noul", "instructions": "About {{ input.topic }}?"}
    node = _node(state="Topic: {{ input.topic }}", questions=[question])
    # Act
    await node.execute(node_input({"topic": "billing"}, context))
    # Assert
    kwargs = client.await_args.kwargs
    assert kwargs["state"] == "Topic: billing"
    assert kwargs["questions"]["q"]["instructions"] == "About billing?"


async def test_state_json_sent_parsed(client, context) -> None:
    # Arrange
    node = _node(state='{"a": 1}')
    # Act
    await node.execute(node_input({}, context))
    # Assert
    assert client.await_args.kwargs["state"] == {"a": 1}


async def test_state_invalid_json_sent_as_string(client, context) -> None:
    # Arrange
    node = _node(state="{not json")
    # Act
    await node.execute(node_input({}, context))
    # Assert
    assert client.await_args.kwargs["state"] == "{not json"


async def test_empty_state_sent(client, context) -> None:
    # Arrange
    node = _node()
    # Act
    await node.execute(node_input({}, context))
    # Assert
    client.assert_awaited_once()
    assert client.await_args.kwargs["state"] == ""


async def test_output_merged_and_passthrough(client, context) -> None:
    # Arrange
    node = _node()
    # Act
    out = await node.execute(node_input({"message": "hi", "x": 1}, context))
    # Assert
    assert out.data["message"] == "hi"
    assert out.data["x"] == 1
    assert out.data["jev"]["intent"] == RESPONSE["answers"]["intent"]
    assert out.data["jev"]["relevant"]["noul"] == 0.9
    assert out.data["jev"]["relevant"]["confidence"] == pytest.approx(0.8)


async def test_custom_output_key(client, context) -> None:
    # Arrange
    node = _node(outputKey="check")
    # Act
    out = await node.execute(node_input({}, context))
    # Assert
    assert "check" in out.data
    assert "jev" not in out.data


async def test_output_key_overrides_existing(client, context) -> None:
    # Arrange
    node = _node()
    # Act
    out = await node.execute(node_input({"jev": "old", "keep": True}, context))
    # Assert
    assert out.data["jev"]["relevant"]["noul"] == 0.9
    assert out.data["keep"] is True


async def test_metadata_cost_and_usage(client, context) -> None:
    # Arrange
    node = _node()
    # Act
    out = await node.execute(node_input({}, context))
    # Assert
    assert out.metadata["cost"] == pytest.approx(0.042)
    assert out.metadata["used_system_key"] is False
    assert out.metadata["usage"] == RESPONSE["usage"]
    assert out.metadata["model"] == "jev-1.14.0"


async def test_long_context_passed(client, context) -> None:
    # Arrange
    node = _node(longContext=True, model="jev-1.14.0")
    # Act
    await node.execute(node_input({}, context))
    # Assert
    assert client.await_args.kwargs["long_context"] is True
    assert client.await_args.kwargs["model"] == "jev-1.14.0"


async def test_typesafe_error_propagates(mocker, context) -> None:
    # Arrange
    mocker.patch("assemblix_api.nodes.jev_node.system_one", side_effect=TypeSafeError("boom"))
    node = _node()
    # Act / Assert
    with pytest.raises(RuntimeError, match="boom"):
        await node.execute(node_input({}, context))


def test_validate_config_returns_schema_errors() -> None:
    # Arrange
    node = _node(questions=[])
    # Act / Assert
    assert node.validate_config()


def test_descriptor_describes_full_config() -> None:
    # Act
    descriptor = JevNode.descriptor()
    # Assert
    assert descriptor.type == "jev"
    assert descriptor.branching is False
    props = {p.name: p for p in descriptor.properties}
    assert {"credentialId", "model", "state", "questions", "longContext", "outputKey"} <= set(
        props
    )
    fields = {f.name: f for f in props["questions"].fields}
    assert {
        "name",
        "type",
        "instructions",
        "trueCriteria",
        "falseCriteria",
        "options",
        "levels",
    } <= set(fields)
    assert {o.value for o in fields["type"].options} == {"noul", "choice", "score"}


def test_registered() -> None:
    # Act / Assert
    assert NodeRegistry().is_registered("jev")
