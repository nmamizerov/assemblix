"""Reading calls back: the history side of Voice Agents.

Separate from ``voice_session_service``, which serves the live call and owns its own
short-lived DB sessions. This one is an ordinary request-scoped service on the usual
API → Service → Repository path.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.voice_session import VoiceSession
from assemblix_api.database.repositories.execution_repository import ExecutionRepository
from assemblix_api.database.repositories.voice_session_repository import VoiceSessionRepository
from assemblix_api.dto.responses.voice_session import (
    VoiceSessionDetailResponse,
    VoiceSessionExecutionResponse,
    VoiceSessionResponse,
    VoiceSessionTranscriptLine,
)


class VoiceSessionHistoryService:
    def __init__(
        self,
        sessions: VoiceSessionRepository,
        executions: ExecutionRepository,
    ) -> None:
        self._sessions = sessions
        self._executions = executions

    async def list_for_agent(
        self, voice_agent_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[VoiceSessionResponse], int]:
        sessions, total = await self._sessions.list_by_agent(
            voice_agent_id, limit=limit, offset=offset
        )
        return [self._to_summary(session) for session in sessions], total

    async def get_detail(self, voice_session_id: UUID) -> tuple[VoiceSessionDetailResponse, UUID]:
        """Return the call and the project it belongs to, for the caller to authorize."""
        session = await self._sessions.get_by_id(voice_session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice session not found",
            )

        executions = await self._executions.get_by_voice_session_id(voice_session_id)
        detail = VoiceSessionDetailResponse(
            **self._to_summary(session).model_dump(),
            transcript=[VoiceSessionTranscriptLine(**line) for line in session.transcript],
            input_tokens=session.input_tokens,
            output_tokens=session.output_tokens,
            executions=[
                VoiceSessionExecutionResponse(
                    id=execution.id,
                    workflow_id=execution.workflow_id,
                    status=execution.status,
                    started_at=execution.started_at,
                    total_credits=float(execution.total_credits),
                )
                for execution in executions
            ],
        )
        return detail, session.project_id

    @staticmethod
    def _to_summary(session: VoiceSession) -> VoiceSessionResponse:
        return VoiceSessionResponse(
            id=session.id,
            voice_agent_id=session.voice_agent_id,
            status=session.status,
            started_at=session.started_at,
            ended_at=session.ended_at,
            duration_sec=session.duration_sec,
            total_credits=float(session.total_credits),
            turn_count=len(session.transcript),
            end_reason=session.end_reason,
        )
