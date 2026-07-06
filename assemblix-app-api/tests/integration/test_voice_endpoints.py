"""Integration tests for capability-filtered voice discovery endpoints."""

from __future__ import annotations


async def test_speech_providers_include_elevenlabs(client, auth_headers) -> None:
    """GET /voice/providers?capability=speech lists elevenlabs."""
    # Arrange / Act
    resp = await client.get("/api/voice/providers?capability=speech", headers=auth_headers)
    # Assert
    assert resp.status_code == 200
    assert any(p["name"] == "elevenlabs" for p in resp.json())


async def test_speech_models_for_elevenlabs(client, auth_headers) -> None:
    """GET /voice/providers/elevenlabs/models?capability=speech returns speech models."""
    # Arrange / Act
    resp = await client.get(
        "/api/voice/providers/elevenlabs/models?capability=speech", headers=auth_headers
    )
    # Assert
    assert resp.status_code == 200
    assert any(m["id"] == "eleven_multilingual_v2" for m in resp.json())
