"""Structured logging configuration via structlog.

JSON output in prod (when stdout is not a tty, e.g. Docker), colored ConsoleRenderer
in dev. Third-party library logs (uvicorn, sqlalchemy, httpx, litellm) are captured
through the root handler and flow through the same pipeline, picking up request_id
from contextvars.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from asgi_correlation_id.context import correlation_id


def _add_request_id(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    rid = correlation_id.get()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(level: str = "INFO", json_logs: bool | None = None) -> None:
    """Configure structlog + the stdlib root handler.

    If json_logs is None it is autodetected (True when stdout is not a tty).
    """
    if json_logs is None:
        json_logs = not sys.stdout.isatty()

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=renderer,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "httpx",
        "litellm",
    ):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True

    logging.getLogger("sqlalchemy.engine").setLevel("WARNING")
