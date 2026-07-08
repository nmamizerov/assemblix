"""Provider dispatch for minting an avatar session token.

Mirrors external/voice/synthesis.py: a thin ``if provider == ...`` seam rather
than a polymorphic base class, matching the existing voice layer. Adding a
provider = one branch here + one adapter module.
"""

from __future__ import annotations

from assemblix_api.external.avatar import anam


async def mint_session(*, provider: str, api_key: str, persona_config: dict) -> str:
    """Mint a client session token for ``provider`` with the given persona."""
    if provider == "anam":
        return await anam.mint_session_token(api_key=api_key, persona_config=persona_config)
    raise NotImplementedError(f"Avatar provider {provider!r} is not supported")
