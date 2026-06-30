"""Notification sender protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Sender(Protocol):
    """
    Sends a message to a specific channel.

    Implementations must raise on send failure so the caller can distinguish
    success from error.
    """

    async def send(self, data: dict, message: str) -> None: ...
