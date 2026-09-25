"""resolve_avatar: one place turns an avatar config into a key + persona."""

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from assemblix_api.schemas.node import WorkflowAvatarConfig
from assemblix_api.services.avatar_service import ResolvedAvatar, resolve_avatar


class _Credentials:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def get_avatar_api_key_with_fallback(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "anam-key"


async def test_resolves_key_and_persona() -> None:
    project_id = uuid4()
    credential_id = str(uuid4())
    credentials = _Credentials()

    resolved = await resolve_avatar(
        WorkflowAvatarConfig(
            provider="anam", avatar_model="cara-4", avatar_id="av-1", credential_id=credential_id
        ),
        project_id=project_id,
        credentials=credentials,
    )

    assert resolved == ResolvedAvatar(
        provider="anam", api_key="anam-key", avatar_id="av-1", avatar_model="cara-4"
    )
    assert credentials.calls == [
        {
            "credentials_id": UUID(credential_id),
            "project_id": project_id,
            "avatar_provider": "anam",
        }
    ]


async def test_missing_avatar_id_is_a_400() -> None:
    with pytest.raises(HTTPException) as exc:
        await resolve_avatar(
            WorkflowAvatarConfig(provider="anam", avatar_model="cara-4"),
            project_id=uuid4(),
            credentials=_Credentials(),
        )
    assert exc.value.status_code == 400
