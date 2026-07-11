import pytest

from assemblix_api.external.avatar import session


@pytest.mark.asyncio
async def test_dispatch_anam(monkeypatch):
    async def _fake_mint(*, api_key, persona_config):
        return f"tok:{api_key}:{persona_config['name']}"

    monkeypatch.setattr(session.anam, "mint_session_token", _fake_mint)

    token = await session.mint_session(
        provider="anam", api_key="k", persona_config={"name": "Cara"}
    )
    assert token == "tok:k:Cara"


@pytest.mark.asyncio
async def test_dispatch_unknown_provider_raises():
    with pytest.raises(NotImplementedError):
        await session.mint_session(provider="nope", api_key="k", persona_config={})
