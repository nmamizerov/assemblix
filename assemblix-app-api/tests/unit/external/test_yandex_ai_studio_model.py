"""Unit tests: Yandex AI Studio transport in the litellm model factory."""

from __future__ import annotations

from typing import Any

import pytest

from assemblix_api.external.llm import litellm_model
from assemblix_api.external.llm.litellm_model import build_litellm_model
from assemblix_api.external.llm.model_catalog import get_provider_descriptor


async def test_yandex_model_is_folder_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The folder from the credential goes into the model URI and the project header."""
    # Arrange
    captured: dict[str, Any] = {}

    async def fake_acompletion(**kwargs: Any) -> Any:
        captured.update(kwargs)
        raise RuntimeError("stop")

    monkeypatch.setattr(litellm_model.litellm, "acompletion", fake_acompletion)
    model = build_litellm_model("yandex_ai_studio", "aliceai-llm", "b1gfolder:AQVNkey")

    # Act
    with pytest.raises(RuntimeError):
        await model.client.chat.completions.create(model=model.model_name, messages=[])

    # Assert
    assert captured["model"] == "openai/gpt://b1gfolder/aliceai-llm"
    assert captured["api_key"] == "AQVNkey"
    assert captured["api_base"] == "https://ai.api.cloud.yandex.net/v1"
    assert captured["extra_headers"] == {"OpenAI-Project": "b1gfolder"}


def test_yandex_credential_without_folder_is_rejected() -> None:
    """A bare API key (no folder) fails fast with a clear error."""
    # Act / Assert
    with pytest.raises(ValueError, match="folderId"):
        build_litellm_model("yandex_ai_studio", "aliceai-llm", "AQVNkey")


def test_yandex_provider_is_registered() -> None:
    """The provider and its models are served to the UI."""
    # Act
    descriptor = get_provider_descriptor("yandex_ai_studio")

    # Assert
    assert descriptor is not None
    assert descriptor.find_model("aliceai-llm") is not None
