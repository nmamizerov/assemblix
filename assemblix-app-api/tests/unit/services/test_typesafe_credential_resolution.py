import uuid

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


def test_typesafe_token_member_exists() -> None:
    # Arrange / Act
    value = CredentialsType.TYPESAFE_TOKEN
    # Assert
    assert value.value == "typesafe_token"


async def test_returns_key_for_owned_typesafe_credential(db_session, auth_user) -> None:
    # Arrange
    service = _service(db_session)
    cred = await _make_credential(
        db_session, auth_user.project_id, CredentialsType.TYPESAFE_TOKEN, "ts-secret"
    )
    # Act
    key = await service.get_typesafe_api_key(cred.id, auth_user.project_id)
    # Assert
    assert key == "ts-secret"


async def test_missing_credential_id_raises_400(db_session, auth_user) -> None:
    # Arrange
    service = _service(db_session)
    # Act / Assert
    with pytest.raises(HTTPException) as exc:
        await service.get_typesafe_api_key(None, auth_user.project_id)
    assert exc.value.status_code == 400


async def test_wrong_type_raises_400(db_session, auth_user) -> None:
    # Arrange
    service = _service(db_session)
    cred = await _make_credential(db_session, auth_user.project_id, CredentialsType.OPENAI_TOKEN)
    # Act / Assert
    with pytest.raises(HTTPException) as exc:
        await service.get_typesafe_api_key(cred.id, auth_user.project_id)
    assert exc.value.status_code == 400


async def test_foreign_project_raises(db_session, auth_user) -> None:
    # Arrange
    service = _service(db_session)
    cred = await _make_credential(
        db_session, auth_user.project_id, CredentialsType.TYPESAFE_TOKEN
    )
    # Act / Assert
    with pytest.raises(HTTPException) as exc:
        await service.get_typesafe_api_key(cred.id, uuid.uuid4())
    assert exc.value.status_code == 403
