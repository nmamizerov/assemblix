"""Cascade call details: stored at close, read back on the session detail."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from assemblix_api.realtime.cascade.setup import CascadeMeter, CascadeSetup, call_details
from assemblix_api.schemas.voice_agent import TurnConfig
from assemblix_api.services.voice_session_history_service import VoiceSessionHistoryService
from assemblix_api.services.voice_session_service import (
    VoiceSessionService,
    compute_session_credits,
)

_LLM_CALL = {
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "effectiveModel": "gpt-4.1-mini-2025",
    "params": {"max_completion_tokens": 200},
    "messages": [
        {"role": "assistant", "content": "Здравствуйте"},
        {"role": "user", "content": "есть сироп?"},
    ],
    "response": "Есть.",
    "inputTokens": 120,
    "outputTokens": 3,
    "cachedInputTokens": 64,
    "costUsd": 0.0002,
    "ttftMs": 410,
    "durationMs": 620,
    "outcome": "ok",
    "error": None,
}
_TURN_USAGE = {
    "sttSeconds": 1.6,
    "sttCostUsdEstimate": 0.000016,
    "llmCostUsd": 0.0002,
    "ttsChars": 5,
    "ttsCostUsd": 0.0005,
}


def _setup() -> CascadeSetup:
    return CascadeSetup(
        stt_provider="yandex",
        stt_model="general",
        stt_api_key="k",
        stt_uses_system_key=True,
        stt_cost_per_minute=0.6,
        turn=TurnConfig(),
        brain_provider="openai",
        brain_model="gpt-4.1-mini",
        brain_api_key="k",
        brain_uses_system_key=True,
        brain_params={"max_completion_tokens": 200},
        history_turns=6,
    )


def _session(transcript: list[dict], details: dict | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        voice_agent_id=uuid4(),
        project_id=uuid4(),
        client_id=None,
        status="completed",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        duration_sec=60.0,
        total_credits=Decimal("1.5"),
        own_key_cost_usd=Decimal("0"),
        transcript=transcript,
        input_tokens=120,
        output_tokens=3,
        end_reason="user_hangup",
        call_details=details,
    )


def _history(session: SimpleNamespace) -> VoiceSessionHistoryService:
    sessions = AsyncMock()
    sessions.get_by_id.return_value = session
    executions = AsyncMock()
    executions.get_by_voice_session_id.return_value = []
    return VoiceSessionHistoryService(sessions, executions)


async def test_close_stores_call_details_with_the_platform_figures() -> None:
    """Instructions, stage config and per-stage spend are written once per call,
    alongside the platform fee and provider margin the call was billed."""
    # Arrange
    setup, meter = _setup(), CascadeMeter(stt_seconds=30.0, brain_cost_usd=Decimal("0.002"))
    details = call_details(
        setup,
        meter,
        instructions="Ты консультант аптеки.",
        tts_provider="elevenlabs",
        tts_model="eleven_flash_v2_5",
        tts_chars=120,
        tts_cost_usd=Decimal("0.012"),
    )
    row = SimpleNamespace(id=uuid4(), voice_agent_id=uuid4(), project_id=uuid4(), transcript=[])
    sessions = AsyncMock()
    sessions.get_by_id.return_value = row
    service = VoiceSessionService(
        voice_agents=AsyncMock(),
        projects=AsyncMock(),
        organizations=AsyncMock(),
        knowledge_bases=AsyncMock(),
        credentials=AsyncMock(),
        sessions=sessions,
        transactions=AsyncMock(),
        credits=AsyncMock(),
    )
    spend = [(Decimal("0.3"), True), (Decimal("0.002"), True)]

    # Act
    await service.close_session(
        voice_session_id=row.id,
        transcript=[],
        duration_sec=60.0,
        end_reason="user_hangup",
        input_tokens=0,
        output_tokens=0,
        cost_per_minute=0.0,
        uses_system_key=False,
        tts_cost_usd=Decimal("0.012"),
        tts_uses_system_key=True,
        extra_costs=spend,
        call_details=details,
    )

    # Assert
    stored = sessions.update.await_args.kwargs["call_details"]
    fee, margin = compute_session_credits(
        60.0,
        0.0,
        uses_system_key=False,
        tts_cost_usd=Decimal("0.012"),
        tts_uses_system_key=True,
        extra_costs=spend,
    )
    assert stored["instructions"] == "Ты консультант аптеки."
    assert stored["brain"] == {
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "params": {"max_completion_tokens": 200},
        "historyTurns": 6,
    }
    assert stored["costs"] == {
        "sttSeconds": 30.0,
        "sttCostUsd": 0.3,
        "llmCostUsd": 0.002,
        "ttsChars": 120,
        "ttsCostUsd": 0.012,
        "platformFeeCredits": float(fee),
        "providerMarginCredits": float(margin),
    }


async def test_detail_exposes_turn_records_and_stage_costs() -> None:
    # Arrange
    transcript = [
        {"role": "user", "text": "есть сироп?"},
        {"role": "assistant", "text": "Есть.", "llmCall": _LLM_CALL, "usage": _TURN_USAGE},
    ]
    details = {
        "instructions": "Ты консультант аптеки.",
        "stt": {"provider": "yandex", "model": "general"},
        "brain": {"provider": "openai", "model": "gpt-4.1-mini", "params": {}, "historyTurns": 6},
        "tts": {"provider": "elevenlabs", "model": "eleven_flash_v2_5"},
        "costs": {
            "sttSeconds": 30.0,
            "sttCostUsd": 0.3,
            "llmCostUsd": 0.002,
            "ttsChars": 120,
            "ttsCostUsd": 0.012,
            "platformFeeCredits": 1.0,
            "providerMarginCredits": 0.5,
        },
    }
    history = _history(_session(transcript, details))

    # Act
    detail, _ = await history.get_detail(uuid4())
    body = detail.model_dump(by_alias=True)

    # Assert
    reply = body["transcript"][1]
    assert reply["llmCall"]["messages"] == _LLM_CALL["messages"]
    assert reply["llmCall"]["cachedInputTokens"] == 64
    assert reply["llmCall"]["ttftMs"] == 410 and reply["llmCall"]["outcome"] == "ok"
    assert reply["usage"] == _TURN_USAGE
    assert body["transcript"][0]["llmCall"] is None
    assert body["callDetails"]["instructions"] == "Ты консультант аптеки."
    assert body["callDetails"]["brain"]["historyTurns"] == 6
    assert body["callDetails"]["costs"] == details["costs"]


async def test_an_old_session_without_records_still_serializes() -> None:
    # Arrange
    transcript = [{"role": "user", "text": "привет"}, {"role": "assistant", "text": "Да"}]
    history = _history(_session(transcript, None))

    # Act
    detail, _ = await history.get_detail(uuid4())
    body = detail.model_dump(by_alias=True)

    # Assert
    assert body["callDetails"] is None
    assert [line["llmCall"] for line in body["transcript"]] == [None, None]
    assert [line["usage"] for line in body["transcript"]] == [None, None]
