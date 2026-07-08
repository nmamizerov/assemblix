"""Debug Event Manager for SSE streaming.

Manages workflow execution events in debug mode and delivers them to clients
via Server-Sent Events. Supports two backends:
  - In-process asyncio.Queue (default, no Redis required).
  - Redis Pub/Sub transport (when redis_transport is supplied), which allows
    SSE to work across multiple replicas.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from assemblix_api.core.settings import get_settings
from assemblix_api.schemas.debug_events import (
    AlignmentData,
    AudioDeltaEventData,
    DebugEvent,
    DebugEventType,
    ErrorEventData,
    ExecutionCompleteEventData,
    StepCompleteEventData,
    StepStartEventData,
    StreamDeltaEventData,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from assemblix_api.execution.debug_pubsub import RedisDebugEventTransport
    from assemblix_api.execution.stream_buffer import (
        InMemoryStreamBuffer,
        RedisStreamBuffer,
    )


class DebugEventManager:
    """Manager for SSE debug-execution streams.

    When *redis_transport* is provided, every emitted event is published to
    Redis and the local asyncio.Queue is bypassed entirely.  When it is None
    (the default), the original in-process queue path is used unchanged.
    """

    def __init__(
        self,
        redis_transport: RedisDebugEventTransport | None = None,
        buffer: InMemoryStreamBuffer | RedisStreamBuffer | None = None,
    ) -> None:
        # execution_id -> asyncio.Queue (used only without Redis transport)
        self._streams: dict[UUID, asyncio.Queue] = {}
        self._client_ready: dict[UUID, asyncio.Event] = {}
        # Optional Redis Pub/Sub transport for cross-replica SSE
        self._redis_transport = redis_transport
        # Sequence-numbered, replayable buffer backing the subscribe-by-id SSE endpoint.
        if buffer is None:
            from assemblix_api.execution.stream_buffer import InMemoryStreamBuffer

            buffer = InMemoryStreamBuffer(
                audio_max_chunks=get_settings().stream_audio_buffer_max_chunks
            )
        self._buffer = buffer

    @property
    def has_redis_transport(self) -> bool:
        """Return True when events are routed through Redis Pub/Sub."""
        return self._redis_transport is not None

    def create_stream(self, execution_id: UUID) -> asyncio.Queue:
        """Create a new event stream for an execution. Raises if one exists."""
        if execution_id in self._streams:
            raise ValueError(f"Stream for execution {execution_id} already exists")

        queue: asyncio.Queue = asyncio.Queue()
        self._streams[execution_id] = queue
        self._client_ready[execution_id] = asyncio.Event()
        self._buffer.open(execution_id)
        return queue

    def get_stream(self, execution_id: UUID) -> asyncio.Queue | None:
        return self._streams.get(execution_id)

    async def emit_event(self, execution_id: UUID, event: DebugEvent) -> None:
        """Emit a debug event.

        When a Redis transport is configured the event is serialised and
        published to the Redis channel for *execution_id*; the local queue is
        not touched.  Without a transport the event is placed on the local
        asyncio.Queue as before.

        The event is first appended to the replayable buffer, which assigns its
        monotonic ``seq`` (used by the subscribe-by-id SSE endpoint).
        """
        await self._buffer.append(execution_id, event)

        if self._redis_transport is not None:
            await self._redis_transport.publish(execution_id, event.model_dump(mode="json"))
            return

        queue = self._streams.get(execution_id)
        if queue:
            await queue.put(event)

    def is_streaming(self, execution_id: UUID) -> bool:
        """Whether a replayable buffer exists for this execution (subscribe target)."""
        return self._buffer.is_open(execution_id)

    def subscribe(self, execution_id: UUID, after_seq: int) -> AsyncIterator[DebugEvent]:
        """Replay buffered events after *after_seq*, then tail live until the terminal event."""
        return self._buffer.subscribe(execution_id, after_seq)

    async def emit_stream_delta(
        self, execution_id: UUID, *, step_number: int, node_id: str, delta: str
    ) -> None:
        """Emit a text-delta event from a streaming agent node."""
        event_data = StreamDeltaEventData(node_id=node_id, step_number=step_number, delta=delta)
        event = DebugEvent(
            event_type=DebugEventType.STREAM_DELTA,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )
        await self.emit_event(execution_id, event)

    async def emit_audio_delta(
        self,
        execution_id: UUID,
        *,
        step_number: int,
        node_id: str,
        audio: str,
        alignment: AlignmentData | None = None,
    ) -> None:
        """Emit a live-only PCM audio chunk from a streaming voice agent node.

        Routed to the buffer's transient path (not the retained log), so heavy PCM never
        starves cursor replay of text/control events.
        """
        event_data = AudioDeltaEventData(
            node_id=node_id, step_number=step_number, audio=audio, alignment=alignment
        )
        event = DebugEvent(
            event_type=DebugEventType.AUDIO_DELTA,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )
        # Transient ring for the subscribe-by-id endpoint (live + tiny replay window; never
        # retained in the cursor-replay log so heavy PCM can't starve text/control).
        await self._buffer.append_transient(execution_id, event)
        # Also deliver live to the inline /execute/debug queue / Redis Pub/Sub transport so
        # that SSE consumer carries audio too. Live-only: the queue is drained, not retained.
        if self._redis_transport is not None:
            await self._redis_transport.publish(execution_id, event.model_dump(mode="json"))
        else:
            queue = self._streams.get(execution_id)
            if queue:
                await queue.put(event)

    def open_buffer(self, execution_id: UUID) -> None:
        """Open the replayable buffer for a streaming-only run (no legacy queue).

        Unlike create_stream, this does NOT allocate an asyncio.Queue — a streaming run is
        consumed via subscribe(), so a queue would just accumulate undrained events.
        """
        self._buffer.open(execution_id)

    def cleanup_stream(self, execution_id: UUID) -> None:
        if execution_id in self._streams:
            del self._streams[execution_id]
        if execution_id in self._client_ready:
            del self._client_ready[execution_id]
        self._buffer.drop(execution_id)

    def schedule_stream_cleanup(self, execution_id: UUID) -> None:
        """Drop the buffer (and any legacy queue) a TTL after the execution completes.

        The delay lets a late or reconnecting subscriber still replay just after the run
        finishes; after the TTL the endpoint 404s and the client falls back to task polling.
        """
        ttl = get_settings().stream_buffer_ttl_seconds

        async def _drop_later() -> None:
            await asyncio.sleep(ttl)
            self.cleanup_stream(execution_id)

        asyncio.create_task(_drop_later())

    def mark_client_ready(self, execution_id: UUID) -> None:
        """Signal that the client connected and is ready to receive events."""
        if execution_id in self._client_ready:
            self._client_ready[execution_id].set()

    async def wait_for_client(self, execution_id: UUID, timeout: float = 10.0) -> bool:
        """Wait for the client to connect; return False on timeout."""
        import asyncio

        if execution_id not in self._client_ready:
            return False

        try:
            await asyncio.wait_for(self._client_ready[execution_id].wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    # Helper methods for typed events

    async def emit_step_start(
        self,
        execution_id: UUID,
        step_number: int,
        node_id: str,
        node_type: str,
        input_data: dict,
        state_before: dict,
        project_state_before: dict,
    ) -> None:
        event_data = StepStartEventData(
            step_number=step_number,
            node_id=node_id,
            node_type=node_type,
            input_data=input_data,
            state_before=state_before,
            project_state_before=project_state_before,
        )

        event = DebugEvent(
            event_type=DebugEventType.STEP_START,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )

        await self.emit_event(execution_id, event)

    async def emit_step_complete(
        self,
        execution_id: UUID,
        step_number: int,
        node_id: str,
        node_type: str,
        output_data: dict | None,
        state_after: dict,
        project_state_after: dict,
        duration_ms: int,
        model_used: str | None = None,
        tokens_used: int | None = None,
        cost: float | None = None,
        own_key_cost_usd: float | None = None,
        credits_used: float | None = None,
        llm_request: list[dict] | None = None,
    ) -> None:
        event_data = StepCompleteEventData(
            step_number=step_number,
            node_id=node_id,
            node_type=node_type,
            output_data=output_data,
            state_after=state_after,
            project_state_after=project_state_after,
            duration_ms=duration_ms,
            model_used=model_used,
            tokens_used=tokens_used,
            cost=cost,
            own_key_cost_usd=own_key_cost_usd,
            credits_used=credits_used,
            llm_request=llm_request,
        )

        event = DebugEvent(
            event_type=DebugEventType.STEP_COMPLETE,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )

        await self.emit_event(execution_id, event)

    async def emit_execution_complete(
        self,
        execution_id: UUID,
        status: str,
        output: dict,
        final_state: dict,
        final_project_state: dict,
        total_steps: int,
        total_credits: Decimal,
        duration_ms: int,
        session_id: UUID | None = None,
        own_key_cost_usd: Decimal | None = None,
        is_session_closed: bool = False,
    ) -> None:
        event_data = ExecutionCompleteEventData(
            status=status,
            output=output,
            final_state=final_state,
            final_project_state=final_project_state,
            total_steps=total_steps,
            total_credits=float(total_credits),  # Decimal -> float for JSON
            duration_ms=duration_ms,
            session_id=session_id,
            own_key_cost_usd=(float(own_key_cost_usd) if own_key_cost_usd is not None else None),
            is_session_closed=is_session_closed,
        )

        event = DebugEvent(
            event_type=DebugEventType.EXECUTION_COMPLETE,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )

        await self.emit_event(execution_id, event)

    async def emit_error(
        self,
        execution_id: UUID,
        error_message: str,
        error_type: str,
        failed_node_id: str | None,
        step_number: int,
    ) -> None:
        event_data = ErrorEventData(
            error_message=error_message,
            error_type=error_type,
            failed_node_id=failed_node_id,
            step_number=step_number,
        )

        event = DebugEvent(
            event_type=DebugEventType.ERROR,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )

        await self.emit_event(execution_id, event)
