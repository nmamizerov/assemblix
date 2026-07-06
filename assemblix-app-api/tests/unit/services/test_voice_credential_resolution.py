import pytest
from fastapi import HTTPException

from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.repositories.credentials_repository import CredentialsRepository
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.enums import PlanTier
from assemblix_api.services.credentials_service import CredentialsService


def _service(db_session) -> CredentialsService:
    return CredentialsService(CredentialsRepository(db_session), OrganizationUserRepository(db_session))


async def _make_credential(db_session, project_id, cred_type, value="secret"):
    repo = CredentialsRepository(db_session)
    return await repo.create(project_id=project_id, type=cred_type, name="c", value=value)


async def test_own_valid_elevenlabs_key_on_paid_plan(db_session, auth_user) -> None:
    """Paid plan + own elevenlabs credential → (user key, is_system=False)."""
    # Arrange
    service = _service(db_session)
    cred = await _make_credential(db_session, auth_user.project_id, CredentialsType.ELEVENLABS_TOKEN, "xi-user")
    # Act
    key, is_system = await service.get_voice_api_key_with_fallback(
        credentials_id=cred.id, project_id=auth_user.project_id,
        voice_provider="elevenlabs", organization_plan=PlanTier.PRO,
    )
    # Assert
    assert key == "xi-user"
    assert is_system is False


async def test_free_plan_forces_system_key(db_session, auth_user, monkeypatch) -> None:
    """FREE plan → system key even if an own credential is passed."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    service = _service(db_session)
    cred = await _make_credential(db_session, auth_user.project_id, CredentialsType.ELEVENLABS_TOKEN, "xi-user")
    # Act
    key, is_system = await service.get_voice_api_key_with_fallback(
        credentials_id=cred.id, project_id=auth_user.project_id,
        voice_provider="elevenlabs", organization_plan=PlanTier.FREE,
    )
    # Assert
    assert key == "xi-system"
    assert is_system is True


async def test_paid_plan_no_credential_falls_back_to_system(db_session, auth_user, monkeypatch) -> None:
    """Paid plan, no credential → system key fallback."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    service = _service(db_session)
    # Act
    key, is_system = await service.get_voice_api_key_with_fallback(
        credentials_id=None, project_id=auth_user.project_id,
        voice_provider="elevenlabs", organization_plan=PlanTier.PRO,
    )
    # Assert
    assert key == "xi-system"
    assert is_system is True


async def test_wrong_type_credential_falls_back_to_system(db_session, auth_user, monkeypatch) -> None:
    """Paid plan + wrong-type credential (openai) → system key fallback."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "xi-system")
    service = _service(db_session)
    cred = await _make_credential(db_session, auth_user.project_id, CredentialsType.OPENAI_TOKEN, "sk-x")
    # Act
    key, is_system = await service.get_voice_api_key_with_fallback(
        credentials_id=cred.id, project_id=auth_user.project_id,
        voice_provider="elevenlabs", organization_plan=PlanTier.PRO,
    )
    # Assert
    assert key == "xi-system"
    assert is_system is True


async def test_no_key_anywhere_raises_503(db_session, auth_user, monkeypatch) -> None:
    """Paid plan, no credential and no system key → 503 (surfaces as a normal run error)."""
    # Arrange
    monkeypatch.setattr(get_settings(), "system_elevenlabs_api_key", "")
    service = _service(db_session)
    # Act / Assert
    with pytest.raises(HTTPException) as exc:
        await service.get_voice_api_key_with_fallback(
            credentials_id=None, project_id=auth_user.project_id,
            voice_provider="elevenlabs", organization_plan=PlanTier.PRO,
        )
    assert exc.value.status_code == 503
