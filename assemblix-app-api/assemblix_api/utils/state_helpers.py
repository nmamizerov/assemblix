"""Helpers for working with state variables."""

import json
from typing import Any


def get_typed_default_value(var_schema: dict) -> Any:
    """Return the schema's default_value, or a typed default based on its type."""
    if var_schema.get("default_value") is not None:
        return var_schema["default_value"]

    type_defaults = {
        "number": 0,
        "string": "",
        "boolean": False,
        "object": {},
    }

    var_type = var_schema.get("type", "string")
    return type_defaults.get(var_type, "")


_BOOL_TRUE_STRINGS = {"true", "1", "yes"}
_BOOL_FALSE_STRINGS = {"false", "0", "no", ""}


def coerce_to_type(value: Any, var_type: str) -> tuple[Any, bool]:
    """Coerce value to the declared variable type ("number" | "string" | "boolean" | "object").

    Returns (coerced_value, success). On failed coercion the original value is returned
    with success=False (the caller decides whether to warn). None and unknown var_types
    pass through unchanged with success=True.
    """
    if value is None:
        return None, True

    if var_type == "string":
        if isinstance(value, str):
            return value, True
        return str(value), True

    if var_type == "number":
        # bool is a subtype of int in Python; treat it as a number explicitly
        if isinstance(value, bool):
            return int(value), True
        if isinstance(value, (int, float)):
            return value, True
        if isinstance(value, str):
            stripped = value.strip()
            try:
                return int(stripped), True
            except ValueError:
                pass
            try:
                return float(stripped), True
            except ValueError:
                return value, False
        return value, False

    if var_type == "boolean":
        if isinstance(value, bool):
            return value, True
        if isinstance(value, (int, float)):
            return bool(value), True
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in _BOOL_TRUE_STRINGS:
                return True, True
            if lowered in _BOOL_FALSE_STRINGS:
                return False, True
            return value, False
        return value, False

    if var_type == "object":
        if isinstance(value, dict):
            return value, True
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                return value, False
            if isinstance(parsed, dict):
                return parsed, True
            return value, False
        return value, False

    # Unknown type: leave the value untouched and report success.
    return value, True
