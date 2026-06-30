# /core/template_evaluator.py
"""Unified rendering of string templates with CEL expressions `{{ ... }}`.

Replaces the duplicated `_evaluate_template` that used to be copied into
`agent_node`, `end_node` and `http_request_node`. The logic is identical: find
`{{expr}}`, evaluate the expression via the CEL-evaluator, substitute the string value.

`fallback_on_error=True` reproduces the behavior of `end_node` — on an evaluation
error, leave the original `{{expr}}` untouched (instead of raising).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assemblix_api.core.cel_evaluator import CELEvaluator
    from assemblix_api.schemas.execution import ExecutionContext

_TEMPLATE_PATTERN = re.compile(r"\{\{(.+?)\}\}")


class TemplateEvaluator:
    """Substitutes CEL expression values into string templates."""

    def __init__(self, cel_evaluator: CELEvaluator):
        self._cel = cel_evaluator

    def render(
        self,
        template: str,
        context: ExecutionContext,
        node_data: dict,
        *,
        fallback_on_error: bool = False,
    ) -> str:
        """Replace each `{{expr}}` with the string value of the evaluated expression.

        Args:
            template: string with zero or more `{{expr}}`.
            context: execution context (passed to CEL as is).
            node_data: node input data (CEL reads it as `input.*`).
            fallback_on_error: when True, an evaluation error leaves `{{expr}}` as is.
        """

        def replace(match: re.Match[str]) -> str:
            expression = match.group(1).strip()
            try:
                value = self._cel.evaluate(expression, context, node_data)
            except Exception:
                if fallback_on_error:
                    return match.group(0)
                raise
            return str(value)

        return _TEMPLATE_PATTERN.sub(replace, template)

    def render_dict(
        self,
        template_dict: dict[str, str],
        context: ExecutionContext,
        node_data: dict,
        *,
        fallback_on_error: bool = False,
    ) -> dict[str, str]:
        """Run `render` over all dict values (keys are left untouched)."""
        return {
            key: self.render(value, context, node_data, fallback_on_error=fallback_on_error)
            for key, value in template_dict.items()
        }
