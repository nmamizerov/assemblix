"""Cascade configuration: what a call resolves to, and what it costs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from assemblix_api.core.settings import get_settings
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.realtime.cascade.setup import CascadeMeter, cascade_spend
from assemblix_api.services.voice_session_service import (
    VoiceSessionService,
    compute_session_credits,
)

_CASCADE_CONFIG = {
    "mode": "cascade",
    "instructions": [{"role": "system", "content": "Ты покупатель."}],
    "tts": {
        "provider": "yandex",
        "model": "yandex-tts-v3-chunk",
        "voiceId": "alena",
        "realtime": True,
    },
    "cascade": {
        "stt": {"provider": "yandex"},
        "turn": {"minSilenceMs": 250},
        "brain": {"type": "prompt", "provider": "gemini", "model": "gemini-2.5-flash-lite"},
    },
}


def _system_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "system_yandex_speechkit_api_key", "AQVN-sys")
    monkeypatch.setattr(settings, "system_yandex_speechkit_folder_id", "b1folder")
    monkeypatch.setattr(settings, "system_gemini_api_key", "g-sys")


async def test_cascade_setup_resolves_stt_brain_and_tts(
    db_session: Any,
    auth_user: Any,
    voice_session_service: VoiceSessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _system_keys(monkeypatch)
    monkeypatch.setattr(
        "assemblix_api.services.voice_session_service.load_turn_models", lambda: object()
    )
    agent = await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id, name="Аптека", config=_CASCADE_CONFIG
    )

    setup = await voice_session_service.build_setup(
        voice_agent_id=agent.id, project_id=auth_user.project_id
    )

    assert setup.provider == "cascade"
    assert setup.cascade is not None
    assert setup.cascade.stt_api_key == "b1folder:AQVN-sys"
    assert setup.cascade.stt_uses_system_key is True
    assert setup.cascade.stt_cost_per_minute == pytest.approx(0.0078)
    assert setup.cascade.brain_provider == "gemini"
    assert setup.cascade.brain_api_key == "g-sys"
    assert setup.cascade.turn.min_silence_ms == 250
    assert setup.tts is not None and setup.tts.model == "yandex-tts-v3-chunk"
    assert "Ты покупатель." in setup.instructions


async def test_missing_turn_models_fail_setup(
    db_session: Any,
    auth_user: Any,
    voice_session_service: VoiceSessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _system_keys(monkeypatch)

    def missing() -> None:
        raise FileNotFoundError("Turn model missing")

    monkeypatch.setattr("assemblix_api.services.voice_session_service.load_turn_models", missing)
    agent = await VoiceAgentRepository(db_session).create(
        project_id=auth_user.project_id, name="Аптека", config=_CASCADE_CONFIG
    )

    with pytest.raises(FileNotFoundError):
        await voice_session_service.build_setup(
            voice_agent_id=agent.id, project_id=auth_user.project_id
        )


def test_cascade_spend_enters_the_margin_only_on_system_keys() -> None:
    from assemblix_api.realtime.cascade.setup import CascadeSetup
    from assemblix_api.schemas.voice_agent import TurnConfig

    setup = CascadeSetup(
        stt_provider="yandex",
        stt_model="general",
        stt_api_key="",
        stt_uses_system_key=True,
        stt_cost_per_minute=0.0078,
        turn=TurnConfig(),
        brain_provider="gemini",
        brain_model="m",
        brain_api_key="",
        brain_uses_system_key=False,
        brain_params={},
        history_turns=40,
    )
    meter = CascadeMeter(stt_seconds=1800, brain_cost_usd=Decimal("0.02"))
    spend = cascade_spend(setup, meter)

    with_extra = compute_session_credits(3600, 0.0, uses_system_key=False, extra_costs=spend)
    without = compute_session_credits(3600, 0.0, uses_system_key=False)

    assert spend[0] == (Decimal("0.234"), True)
    assert with_extra[0] == without[0]  # platform fee unchanged
    assert with_extra[1] > without[1]  # STT on the system key adds margin
    only_brain = compute_session_credits(3600, 0.0, uses_system_key=False, extra_costs=[spend[1]])
    assert only_brain[1] == without[1]  # own-key brain spend adds none
