# /tools/registry.py
"""Registry of tools by string name (modeled after NodeRegistry).

Previously tools were hardcoded in `AgentNode.AVAILABLE_TOOLS` with special
initialization. Now a tool is registered by a factory `@register_tool("name")` — the
factory receives a `ToolContext` (settings, etc.) and returns a `BaseTool` instance.
This provides an extension point for future community tools and for injecting
credentials at creation time.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import structlog

from assemblix_api.core.settings import Settings
from assemblix_api.tools import BaseTool

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ToolContext:
    """Tool creation context. Extension point (per-tenant credentials, etc. — later)."""

    settings: Settings


ToolFactory = Callable[[ToolContext], BaseTool]


class ToolNotRegisteredError(KeyError):
    """An unregistered tool was requested."""


class ToolRegistry:
    """Singleton registry of tool factories."""

    _instance: ToolRegistry | None = None
    _factories: dict[str, ToolFactory] = {}

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, name: str, factory: ToolFactory) -> None:
        self._factories[name] = factory

    def create(self, name: str, ctx: ToolContext) -> BaseTool:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise ToolNotRegisteredError(name) from exc
        return factory(ctx)

    def is_registered(self, name: str) -> bool:
        return name in self._factories

    def registered_names(self) -> list[str]:
        return list(self._factories)

    def clear(self) -> None:
        """Clear the registry (for tests)."""
        self._factories.clear()


registry = ToolRegistry()


def register_tool(name: str) -> Callable[[ToolFactory], ToolFactory]:
    """Decorator that registers a tool factory under a string name."""

    def decorator(factory: ToolFactory) -> ToolFactory:
        registry.register(name, factory)
        return factory

    return decorator
