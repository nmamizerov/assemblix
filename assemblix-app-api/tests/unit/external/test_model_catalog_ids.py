from collections import Counter
from pathlib import Path

import pytest

from assemblix_api.external.llm.models_loader import load_models

_MODELS_DIR = Path(__file__).parents[3] / "assemblix_api" / "external" / "llm" / "models"


@pytest.mark.parametrize("filename", sorted(p.name for p in _MODELS_DIR.glob("*.json")))
def test_model_ids_are_unique(filename: str) -> None:
    # Arrange / Act
    ids = Counter(m.id for m in load_models(filename))
    # Assert — a duplicate id silently overrides the other entry's pricing
    assert [model_id for model_id, count in ids.items() if count > 1] == []
