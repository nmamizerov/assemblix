import pytest
from fastapi import HTTPException

from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.repositories.credentials_repository import CredentialsRepository
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.services.credentials_service import CredentialsService


def _service(db_session) -> CredentialsService:
    return CredentialsService(
        CredentialsRepository(db_session), OrganizationUserRepository(db_session)
    )


async def _make_credential(db_session, project_id, cred_type, value="secret"):
    repo = CredentialsRepository(db_session)
    return await repo.create(project_id=project_id, type=cred_type, name="c", value=value)


async def test_resolves_byo_anam_key(db_session, auth_user) -> None:
    """Own anam credential → the decrypted BYO key (no system fallback for avatars)."""
    # Arrange
    service = _service(db_session)
    cred = await _make_credential(
        db_session, auth_user.project_id, CredentialsType.ANAM_TOKEN, "anam-secret"
    )
    # Act
    key = await service.get_avatar_api_key_with_fallback(
        credentials_id=cred.id,
        project_id=auth_user.project_id,
        avatar_provider="anam",
    )
    # Assert
    assert key == "anam-secret"


async def test_missing_credential_raises_400(db_session, auth_user) -> None:
    """No credential supplied → hard 400, avatars have no system-key fallback."""
    # Arrange
    service = _service(db_session)
    # Act / Assert
    with pytest.raises(HTTPException) as exc:
        await service.get_avatar_api_key_with_fallback(
            credentials_id=None,
            project_id=auth_user.project_id,
            avatar_provider="anam",
        )
    assert exc.value.status_code == 400
