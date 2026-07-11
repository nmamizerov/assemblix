from assemblix_api.database.models.credentials import CredentialsType


def test_anam_token_member_exists():
    # Arrange / Act
    value = CredentialsType.ANAM_TOKEN
    # Assert
    assert value.value == "anam_token"
