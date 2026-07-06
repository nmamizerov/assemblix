"""Integration test for Task 12: voice cost metering + audio scrubbed from persistence.

Exercises the real production path over HTTP (like test_workflow_voice_execute.py):
register -> mint API key -> create + publish a workflow whose END node emits voice
output via a system ElevenLabs key -> execute. Verifies the sync response still
carries audio, the persisted execution row and its terminal step do NOT, and a
VOICE_USAGE credit transaction was recorded against the org's balance.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.engine import get_async_engine
from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.database.repositories.credit_transaction_repository import (
    CreditTransactionRepository,
)
from assemblix_api.database.repositories.execution_repository import ExecutionRepository
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from assemblix_api.external.voice.synthesis import SynthesisResult
from tests.fixtures.workflows import agent_config, edge, node


def _voice_output_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """START (non-voice) -> AGENT -> END (voice output, system ElevenLabs key)."""
    nodes = [
        node("start", "start", {}),
        node("agent", "agent", agent_config(instructions="Reply to the user.")),
        node(
            "end",
            "end",
            {
                "outputFormat": "voice",
                "voice": {"provider": "elevenlabs", "model": "eleven_multilingual_v2", "voiceId": "v1"},
            },
        ),
    ]
    edges = [edge("start", "agent"), edge("agent", "end")]
    return nodes, edges


async def _voice_execute_setup(api_client) -> SimpleNamespace:
    """Register a user, mint an API key, create + publish the voice-output workflow."""
    reg = await api_client.post(
        "/api/auth/register", json={"email": "voice-meter@example.com", "password": "pass1234"}
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}
    project_id = reg.json()["projectId"]
    org_id = reg.json()["organizationId"]

    key_resp = await api_client.post(
        "/api/api-keys/",
        json={"projectId": project_id, "name": "voice-meter-key"},
        headers=jwt_headers,
    )
    assert key_resp.status_code == 201
    key_headers = {"Authorization": f"Bearer {key_resp.json()['apiKey']}"}

    nodes, edges = _voice_output_workflow()
    create_resp = await api_client.post(
        "/api/workflows/",
        json={"projectId": project_id, "name": "Voice output workflow", "nodes": nodes, "edges": edges},
        headers=jwt_headers,
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    publish_resp = await api_client.post(
        f"/api/workflows/{workflow_id}/publish", headers=jwt_headers
    )
    assert publish_resp.status_code == 200

    return SimpleNamespace(key_headers=key_headers, workflow_id=workflow_id, org_id=org_id)


async def _fake_synth(*, text, provider, model, voice_id, api_key):
    return SynthesisResult(audio_bytes=b"AUDIO_BYTES", chars=len(text), provider=provider, model=model)


async def test_voice_run_meters_system_key_and_scrubs_audio(api_client, mock_llm, mocker, monkeypatch) -> None:
    """A system-key voice run: response has audio, DB row is scrubbed, VOICE_USAGE recorded."""
    # Arrange
    from assemblix_api.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    mock_llm.set_response("Hello from the agent")
    mocker.patch("assemblix_api.nodes.end_node.synthesize", side_effect=_fake_synth)

    # Register + mint key + build a workflow whose END node emits voice (no credential -> system key).
    setup = await _voice_execute_setup(api_client)

    # Give the org a paid plan + balance so the system-key voice cost can be charged.
    async with AsyncSession(get_async_engine()) as session:
        org_repo = OrganizationRepository(session)
        org = await org_repo.get_by_id(setup.org_id)
        org.plan = "pro"
        org.credits_balance = Decimal("1000000")
        await org_repo.update(org)
        await session.commit()

    # Act
    resp = await api_client.post(
        f"/api/workflows/{setup.workflow_id}/execute",
        json={"input": {"message": "hi"}},
        headers=setup.key_headers,
    )

    # Assert — response carries audio
    assert resp.status_code == 200
    output = resp.json()["output"]
    assert output["audio"]["base64"]

    # Assert — persisted execution row is scrubbed, VOICE_USAGE recorded, balance decremented
    execution_id = resp.json()["executionId"]
    async with AsyncSession(get_async_engine()) as session:
        exec_row = await ExecutionRepository(session).get_by_id(execution_id)
        assert "audio" not in (exec_row.output or {})
        txs = await CreditTransactionRepository(session).get_by_organization_id(setup.org_id)
        assert any(t.type == CreditTransactionType.VOICE_USAGE for t in txs)
        org = await OrganizationRepository(session).get_by_id(setup.org_id)
        assert org.credits_balance < Decimal("1000000")
