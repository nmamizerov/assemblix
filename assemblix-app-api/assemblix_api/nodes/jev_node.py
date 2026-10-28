"""Jev node — one TypeSafe System One request (yes/no, choice and score questions).

Linear: answers are merged into the output under ``outputKey`` and a following
CONDITION node does the branching (e.g. ``input.jev.relevant.noul > 0.7``).
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from assemblix_api.core.node_registry import register_node
from assemblix_api.external.typesafe import TypeSafeError, system_one
from assemblix_api.schemas.execution import NodeInput, NodeOutput
from assemblix_api.schemas.node import (
    JEV_DEFAULT_STATE,
    BaseNode,
    JevNodeConfig,
    JevQuestionConfig,
)
from assemblix_api.schemas.node_descriptor import (
    NodeDescriptor,
    NodeDisplayCondition,
    NodeProperty,
    NodePropertyOption,
)

JEV_INPUT_PRICE_PER_TOKEN = Decimal("0.042") / 1_000_000


def _parse_state(rendered: str) -> Any:
    if rendered.strip().startswith(("{", "[")):
        try:
            return json.loads(rendered)
        except json.JSONDecodeError:
            pass
    return rendered


@register_node("jev")
class JevNode(BaseNode):
    def __init__(self, node_config: dict) -> None:
        super().__init__(node_config)
        self.typed_config = JevNodeConfig(**node_config["config"])

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        cfg = self.typed_config
        context = node_input.context
        assert context.credential_service is not None
        api_key = await context.credential_service.get_typesafe_api_key(
            UUID(cfg.credential_id) if cfg.credential_id else None, context.project_id
        )

        def render(template: str) -> str:
            return context.templates.render(template, context, node_input.data)

        # The default template must not fail on runs whose input has no message.
        if cfg.state == JEV_DEFAULT_STATE:
            rendered_state = str(node_input.data.get("message", ""))
        else:
            rendered_state = render(cfg.state)
        questions = {q.name: self._question_body(q, render) for q in cfg.questions}
        started = time.monotonic()
        try:
            response = await system_one(
                api_key=api_key,
                model=cfg.model,
                state=_parse_state(rendered_state),
                questions=questions,
                long_context=cfg.long_context,
            )
        except TypeSafeError as e:
            raise RuntimeError(f"Jev request failed: {e}") from e

        answers = response.get("answers", {})
        for answer in answers.values():
            if answer.get("type") == "noul":
                answer["confidence"] = abs(2 * answer["noul"] - 1)

        usage = response.get("usage", {})
        cost = Decimal(usage.get("input_tokens", 0)) * JEV_INPUT_PRICE_PER_TOKEN
        return NodeOutput(
            data={**node_input.data, cfg.output_key: answers},
            metadata={
                "model": response.get("model", cfg.model),
                "usage": usage,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "cost": float(cost),
                "used_system_key": False,
            },
        )

    @staticmethod
    def _question_body(q: JevQuestionConfig, render) -> dict:
        body: dict[str, Any] = {"type": q.type, "instructions": render(q.instructions)}
        if q.type == "noul":
            criteria = {
                k: v for k, v in (("true", q.true_criteria), ("false", q.false_criteria)) if v
            }
            if criteria:
                body["criteria"] = criteria
        elif q.type == "choice":
            body["criteria"] = {o.name: o.description for o in q.options}
        else:
            body["criteria"] = q.levels
        return body

    def validate_config(self) -> list[str]:
        return self.typed_config.validation_errors()

    @classmethod
    def descriptor(cls) -> NodeDescriptor:
        def for_types(*types: str) -> NodeDisplayCondition:
            return NodeDisplayCondition(field="type", values=list(types))

        return NodeDescriptor(
            type="jev",
            display_name="Jev",
            description=(
                "Ask TypeSafe Jev typed questions (yes/no, choice, score) about text. "
                "Answers are added to the output; branch on them with a following Condition."
            ),
            category="logic",
            icon="ScanSearch",
            color="node-logic",
            properties=[
                NodeProperty(
                    name="credentialId",
                    display_name="TypeSafe credential",
                    type="credential",
                    required=True,
                    description="A typesafe_token credential (own key; no system key).",
                ),
                NodeProperty(
                    name="model",
                    display_name="Model",
                    type="string",
                    default="jev-latest",
                    description="jev-latest, or a pinned version such as jev-1.14.0.",
                ),
                NodeProperty(
                    name="state",
                    display_name="State",
                    type="text",
                    default=JEV_DEFAULT_STATE,
                    description=(
                        "The content every question is asked about. Supports {{ cel }} "
                        "templates; a result that is valid JSON is sent as JSON."
                    ),
                ),
                NodeProperty(
                    name="questions",
                    display_name="Questions",
                    type="collection",
                    required=True,
                    description=(
                        "Each answer is available as input.<outputKey>.<name>: noul → "
                        ".noul (probability of yes) and .confidence; choice → .choice, "
                        ".probabilities, .confidence; score → .score, .probabilities, "
                        ".confidence, .legend."
                    ),
                    fields=[
                        NodeProperty(
                            name="name",
                            display_name="Name",
                            type="string",
                            required=True,
                            description="Identifier used in CEL: letters, digits, underscores.",
                        ),
                        NodeProperty(
                            name="type",
                            display_name="Type",
                            type="options",
                            required=True,
                            default="noul",
                            options=[
                                NodePropertyOption(value="noul", label="Yes / no"),
                                NodePropertyOption(value="choice", label="Choice"),
                                NodePropertyOption(value="score", label="Score"),
                            ],
                        ),
                        NodeProperty(
                            name="instructions",
                            display_name="Question",
                            type="text",
                            description="The question or statement. Supports {{ cel }} templates.",
                        ),
                        NodeProperty(
                            name="trueCriteria",
                            display_name="Counts as yes",
                            type="string",
                            show_when=for_types("noul"),
                            description="noul only, optional.",
                        ),
                        NodeProperty(
                            name="falseCriteria",
                            display_name="Counts as no",
                            type="string",
                            show_when=for_types("noul"),
                            description="noul only, optional.",
                        ),
                        NodeProperty(
                            name="options",
                            display_name="Options",
                            type="collection",
                            show_when=for_types("choice"),
                            description="choice only: 1–255 options with unique names.",
                            fields=[
                                NodeProperty(
                                    name="name", display_name="Name", type="string", required=True
                                ),
                                NodeProperty(
                                    name="description",
                                    display_name="When it applies",
                                    type="string",
                                ),
                            ],
                        ),
                        NodeProperty(
                            name="levels",
                            display_name="Levels",
                            type="json",
                            show_when=for_types("score"),
                            description=(
                                "score only: ordered list of 2–10 level descriptions "
                                "(JSON array of strings); index = score."
                            ),
                        ),
                    ],
                ),
                NodeProperty(
                    name="longContext",
                    display_name="Long context",
                    type="boolean",
                    default=False,
                    description="Raise the limit to 262k tokens (slower, less accurate).",
                ),
                NodeProperty(
                    name="outputKey",
                    display_name="Output key",
                    type="string",
                    default="jev",
                    description="Key the answers are written under in the output.",
                ),
            ],
        )
