"""Locale-specific default strings for new workflows (English only)."""

from __future__ import annotations

WORKFLOW_DEFAULTS: dict[str, dict[str, str]] = {
    "en": {
        "workflow_name": "New Workflow",
        "agent_node_name": "Agent",
        "agent_instruction": "You are a helpful assistant that helps the user with their tasks",
        "end_node_name": "Result",
    },
}

SUPPORTED_LANGUAGES = frozenset(WORKFLOW_DEFAULTS.keys())


def get_workflow_defaults(language: str) -> dict[str, str]:
    """Return the default workflow strings for a language, falling back to English."""
    return WORKFLOW_DEFAULTS.get(language, WORKFLOW_DEFAULTS["en"])
