"""API test: the server config endpoint exposes system-key presence + flags."""

from __future__ import annotations


async def test_get_config(client, auth_user, auth_headers) -> None:
    """GET /api/config → 200 with per-provider key flags and billingEnabled."""
    # Act
    resp = await client.get("/api/config", headers=auth_headers)

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["systemApiKeys"].keys()) == {
        "openai",
        "gemini",
        "deepseek",
        "elevenlabs",
    }
    assert all(isinstance(v, bool) for v in body["systemApiKeys"].values())
    assert isinstance(body["billingEnabled"], bool)


async def test_get_config_requires_auth(client, auth_user) -> None:
    """Without credentials the config endpoint is rejected (401/403)."""
    # Act
    resp = await client.get("/api/config")

    # Assert
    assert resp.status_code in (401, 403)
