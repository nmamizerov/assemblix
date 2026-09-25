"""Whether a call can run: the token's room and the agent's avatar must agree."""

from assemblix_api.api.rest.voice_sessions import avatar_call_mismatch
from assemblix_api.services.avatar_service import ResolvedAvatar

_AVATAR = ResolvedAvatar(provider="anam", api_key="k", avatar_id="a", avatar_model="m")


def test_plain_voice_call() -> None:
    assert avatar_call_mismatch(None, None) is None


def test_avatar_call() -> None:
    assert avatar_call_mismatch("va-1", _AVATAR) is None


def test_avatar_removed_after_the_token_was_minted() -> None:
    # The client already joined LiveKit and waits for a face: fail loudly.
    assert avatar_call_mismatch("va-1", None) == "avatar_unavailable"


def test_avatar_added_after_a_voice_token_was_minted() -> None:
    # The client speaks the plain WS protocol: run the call without a face.
    assert avatar_call_mismatch(None, _AVATAR) is None
