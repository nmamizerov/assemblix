"""
JSON provider registry loader.

Each provider has a `models/<provider>.json` file with the shape:

```
{
  "paramSchema": [
    {"name": "temperature", "label": "...", "type": "number", "default": 0.7,
     "hide": {"capability": ["reasoning"]}},
    ...
  ],
  "models": [
    {"id": "...", "label": "...", "contextWindow": ...,
     "maxOutputTokens": ..., "inputCostPerMillion": ...,
     "outputCostPerMillion": ..., "capabilities": {...}},
    ...
  ]
}
```

The loader returns a `ProviderData` value object so providers can ship
both their model registry AND their parameter schema as data, not code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from assemblix_api.external.llm.base import ModelMetadata, ParamDef

_MODELS_DIR = Path(__file__).parent / "models"


@dataclass(frozen=True)
class ProviderData:
    """Bundle of static provider metadata loaded from a single JSON file."""

    models: list[ModelMetadata]
    param_schema: list[ParamDef]


def load_provider_data(filename: str) -> ProviderData:
    """Load and validate a provider's full registry JSON file.

    Args:
        filename: e.g. "openai.json" — relative to `external/llm/models/`.

    Raises:
        FileNotFoundError: if the registry file is missing.
        pydantic.ValidationError: if any entry fails validation.
    """
    path = _MODELS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Provider registry not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    models = [ModelMetadata.model_validate(entry) for entry in data["models"]]
    raw_params = data.get("paramSchema", [])
    param_schema = [ParamDef.model_validate(entry) for entry in raw_params]

    return ProviderData(models=models, param_schema=param_schema)


def load_models(filename: str) -> list[ModelMetadata]:
    """Backwards-compatible shortcut for callers that only need the models."""
    return load_provider_data(filename).models
