"""HTTP access log middleware built on structlog.

Measures request duration and logs method / path / status_code / duration_ms /
client_ip. Must sit *inside* CorrelationIdMiddleware so that request_id is already
in contextvars by the time logging happens.
"""

from __future__ import annotations

import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger("http")


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else None

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "http.request.completed",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )
