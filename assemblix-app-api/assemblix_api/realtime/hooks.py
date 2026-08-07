"""Analysis hooks: the graph engine attached to a conversation, one step behind.

A hook is an ordinary workflow started through the ordinary execute path. There is
no new node type and no voice-specific machinery inside the engine — only an
``input_data`` shape and a ``voice_session_id`` stamped on the execution row so the
call and its runs can be read back together.

Two rules make this safe to hang off a live conversation:

* **Nothing is awaited.** A per-turn run is fired and forgotten; the caller keeps
  talking while it works.
* **Nothing propagates.** A hook that fails is logged and dropped. It must not be
  able to end a call or reach the browser.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

WorkflowRunner = Callable[..., Awaitable[None]]


def _default_runner(**kwargs: Any) -> Awaitable[None]:
    from assemblix_api.dependencies import run_workflow_isolated

    return run_workflow_isolated(**kwargs)


class TurnDispatcher:
    """Starts the configured hook workflows for one call."""

    def __init__(
        self,
        *,
        voice_session_id: UUID,
        turn_workflow_id: str | None,
        final_workflow_id: str | None,
        runner: WorkflowRunner | None = None,
    ) -> None:
        self._voice_session_id = voice_session_id
        self._turn_workflow_id = turn_workflow_id
        self._final_workflow_id = final_workflow_id
        self._runner = runner or _default_runner
        # asyncio holds only weak references to tasks; without this the garbage
        # collector can cancel a hook mid-run.
        self._tasks: set[asyncio.Task] = set()

    def dispatch_turn(self, *, user_text: str, agent_reply: str | None, turn_index: int) -> None:
        """Fire the per-turn workflow. Returns immediately, by design."""
        if not self._turn_workflow_id:
            return
        self._spawn(
            self._turn_workflow_id,
            {
                "message": user_text,
                "voice": {
                    "session_id": str(self._voice_session_id),
                    "turn_index": turn_index,
                    "agent_reply": agent_reply,
                },
            },
        )

    async def dispatch_final(
        self,
        *,
        transcript: list[dict],
        duration_sec: float,
        end_reason: str,
    ) -> None:
        """Run the final workflow once, with the whole conversation as input."""
        if not self._final_workflow_id:
            return
        await self._run(
            self._final_workflow_id,
            {
                "message": self.transcript_as_text(transcript),
                "voice": {
                    "session_id": str(self._voice_session_id),
                    "transcript": transcript,
                    "duration_sec": duration_sec,
                    "end_reason": end_reason,
                },
            },
        )

    @staticmethod
    def transcript_as_text(transcript: list[dict]) -> str:
        return "\n".join(f"{line['role']}: {line['text']}" for line in transcript)

    def _spawn(self, workflow_id: str, input_data: dict) -> None:
        task = asyncio.create_task(self._run(workflow_id, input_data))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, workflow_id: str, input_data: dict) -> None:
        try:
            await self._runner(
                workflow_id=UUID(workflow_id),
                input_data=input_data,
                token_id=None,
                chat_session_id=None,
                voice_session_id=self._voice_session_id,
            )
        except Exception as exc:  # noqa: BLE001 — a hook must never affect the call.
            logger.warning(
                "voice.hook.failed",
                workflow_id=workflow_id,
                voice_session_id=str(self._voice_session_id),
                error=str(exc),
            )
