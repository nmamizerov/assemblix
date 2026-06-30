"""Built-in node import + out-of-tree plugin discovery via entry points.

Third-party packages register node types by declaring:

    [project.entry-points."assemblix.nodes"]
    my_nodes = "my_package.nodes"

``ep.load()`` imports the module, which fires every ``@register_node`` decorator
inside it automatically. An optional ``:attribute`` target (e.g. ``:register``)
also works if you prefer an explicit callable, but is not required.
"""

from __future__ import annotations

from importlib.metadata import entry_points

import structlog

logger = structlog.get_logger(__name__)
ENTRY_POINT_GROUP = "assemblix.nodes"


def load_builtin_nodes() -> None:
    import assemblix_api.nodes  # noqa: F401  (decorators register on import)


def _entry_points():
    return list(entry_points(group=ENTRY_POINT_GROUP))


def load_plugin_nodes() -> list[str]:
    """Sweep entry points in group ``assemblix.nodes`` and load each one.

    Never raises — a broken plugin is logged and skipped so startup always
    completes. Returns the names of successfully loaded entry points.
    """
    loaded: list[str] = []
    for ep in _entry_points():
        try:
            ep.load()
            loaded.append(ep.name)
            logger.info("nodes.plugin_loaded", name=ep.name)
        except Exception as exc:  # never crash startup on a bad plugin
            logger.warning("nodes.plugin_load_failed", name=ep.name, error=str(exc))
    return loaded
