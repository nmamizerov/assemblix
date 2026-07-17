from assemblix_api.external.llm.model_catalog import find_model_metadata


def test_gemini_flash_accepts_audio() -> None:
    # Arrange / Act
    meta = find_model_metadata("gemini", "gemini-3-flash-preview")
    # Assert
    assert meta is not None
    assert meta.capabilities.accepts_audio is True


def test_deepseek_does_not_accept_audio() -> None:
    # Arrange / Act
    meta = find_model_metadata("deepseek", "deepseek-chat")
    # Assert
    assert meta is not None
    assert meta.capabilities.accepts_audio is False
