# AI Avatars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI avatars (anam.ai first) as a third agent-output modality driving a real-time, lip-synced conversational avatar, exposed through a provider-independent API.

**Architecture:** Arch A — the **client** orchestrates. The backend only (a) mints a provider session token from the workflow-level avatar config and (b) reuses the existing phase-2a text-streaming SSE, tagging deltas from avatar-output nodes. The browser renders the avatar over WebRTC (provider SDK) and forwards tagged text deltas into the SDK's `streamMessageChunk`. Our STT (`voice_gate`) transcribes the user's turn — provider STT is never used. Avatars are **BYO-key only** this phase (no system key, no metering).

**Tech Stack:** Backend — Python 3.13, FastAPI, async SQLAlchemy, httpx, pytest. Frontend — React 19, TypeScript, RTK Query, i18next, `@anam-ai/js-sdk`.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-08-ai-avatars-design.md`.
- **Reuse the voice seam verbatim** — mirror `external/voice/` structure, `credentials_service` fallback shape, `api/rest/voice.py` router, and the frontend `voice-model` entity + `VoiceOutputPicker`.
- **BYO-key only:** `get_avatar_api_key_with_fallback` resolves the user's `ANAM_TOKEN` credential and raises if missing/incompatible. No system key, no `AVATAR_USAGE`, no billing-pipeline changes.
- **Reuse phase-2a streaming** (`STREAM_DELTA` SSE) as-is; the `AUDIO_DELTA`/PCM path (2b) does **not** participate.
- **No per-turn length limit** on the avatar path.
- **Backend TDD** (test first), AAA pattern, `./makemigrations.sh` for migrations (never `alembic revision` by hand), packages via `uv add`, `.venv` active.
- **Frontend has no unit tests** — the gate is `npm run build` (type-check) plus manual dogfood. All user-facing text via i18n (`t("key")`); backend snake_case ↔ frontend camelCase is automatic.
- **All comments/docstrings in English**, minimal and only for non-trivial logic.
- **anam facts:** session token `POST {anam_base}/v1/auth/session-token` with `personaConfig` (`name`, `avatarId`, `avatarModel`, `voiceId`, `llmId`), `llmId: "CUSTOMER_CLIENT_V1"` disables anam's brain. Speaking is client-side: `createTalkMessageStream()` → `streamMessageChunk(text, isFinal)` → `endMessage()`; render via `streamToVideoElement`.

---

## File Structure

**Backend (new):**
- `assemblix_api/external/avatar/base.py` — `AvatarModelMetadata`.
- `assemblix_api/external/avatar/avatar_catalog.py` — `AVATAR_PROVIDER_LABELS`, find/list.
- `assemblix_api/external/avatar/models/anam.json` — avatar catalog data.
- `assemblix_api/external/avatar/anam.py` — httpx adapter: `mint_session_token`, `list_avatars`.
- `assemblix_api/external/avatar/session.py` — provider dispatch: `mint_session`.
- `assemblix_api/dto/responses/avatar.py` — discovery + session response DTOs.
- `assemblix_api/api/rest/avatar.py` — discovery + session-mint router.
- `assemblix_api/services/avatar_service.py` — build persona + mint via resolved key.

**Backend (modified):**
- `database/models/credentials.py` — `CredentialsType.ANAM_TOKEN`.
- `services/credentials_service.py` — `get_avatar_api_key_with_fallback`.
- `core/settings.py` — `anam_api_base_url`.
- `schemas/node.py` — `WorkflowAvatarConfig`, `output_type` += `"avatar"`.
- `nodes/agent_node.py` — validation warning when avatar output but no workflow avatar config (via executor context; see Task 11).
- `schemas/debug_events.py` — `StreamDeltaEventData.avatar`.
- `execution/debug_event_manager.py` — `emit_stream_delta(..., avatar=False)`.
- `execution/node_runner.py` — thread avatar flag into the delta sink.
- `dependencies.py` — register avatar service.
- `main.py` (or router registry) — mount `/api/avatar`.

**Frontend (new):**
- `src/entities/avatar-model/` — `api/avatar-model.api.ts`, `model/types.ts`, `index.ts`.
- `.../node-forms/avatar-output-picker.tsx` — provider→credential→avatar cascade.
- `.../workflow-editor/lib/use-avatar-session.ts` — mint + connect + forward deltas.
- `.../workflow-editor/lib/avatar-renderer/` — `types.ts` (`AvatarRenderer`), `anam-renderer.ts`.

**Frontend (modified):**
- `entities/credential/lib/provider-credential-type.ts` — anam mapping.
- `entities/workflow/model/types.ts` — `WorkflowAvatarConfig`, `output_type` += `"avatar"`.
- `.../node-forms/agent-node-form.tsx` — third output option + warning.
- workflow editor header — avatar config entry point.
- `shared/api/baseApi.ts` — `AvatarModels` tag type.
- `shared/i18n/locales/{en,es,ru}.json` — avatar keys.

---

## Task 1: `CredentialsType.ANAM_TOKEN` + migration

**Files:**
- Modify: `assemblix_api/database/models/credentials.py:18-23`
- Test: `tests/unit/test_credentials_type.py` (new)

**Interfaces:**
- Produces: `CredentialsType.ANAM_TOKEN == "anam_token"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_credentials_type.py
from assemblix_api.database.models.credentials import CredentialsType


def test_anam_token_member_exists():
    # Arrange / Act
    value = CredentialsType.ANAM_TOKEN
    # Assert
    assert value.value == "anam_token"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_credentials_type.py -v`
Expected: FAIL — `AttributeError: ANAM_TOKEN`.

- [ ] **Step 3: Add the enum member**

```python
class CredentialsType(str, Enum):
    OPENAI_TOKEN = "openai_token"
    ANTHROPIC_TOKEN = "anthropic_token"
    GEMINI_TOKEN = "gemini_token"
    DEEPSEEK_TOKEN = "deepseek_token"
    ELEVENLABS_TOKEN = "elevenlabs_token"
    ANAM_TOKEN = "anam_token"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_credentials_type.py -v`
Expected: PASS.

- [ ] **Step 5: Create the migration**

The `type` column is a plain enum stored as string (`Mapped[CredentialsType]`), so this is additive with no data change. Generate the migration:

Run: `./makemigrations.sh "add anam_token credentials type" --upgrade`
Expected: a new file under `alembic/versions/`, applied to the local DB.

- [ ] **Step 6: Commit**

```bash
git add assemblix_api/database/models/credentials.py tests/unit/test_credentials_type.py alembic/versions/
git commit -m "feat(avatars): add ANAM_TOKEN credentials type"
```

---

## Task 2: Avatar catalog (`base.py`, `avatar_catalog.py`, `models/anam.json`)

**Files:**
- Create: `assemblix_api/external/avatar/__init__.py` (empty), `base.py`, `avatar_catalog.py`, `models/anam.json`
- Test: `tests/unit/test_avatar_catalog.py`

**Interfaces:**
- Produces:
  - `AvatarModelMetadata(id, label, avatar_model, description=None, cost_per_minute=None)`
  - `AVATAR_PROVIDER_LABELS: dict[str, str]`
  - `find_avatar_model(provider, model) -> AvatarModelMetadata | None`
  - `list_avatar_models(provider) -> list[AvatarModelMetadata]`
  - `list_avatar_providers() -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_avatar_catalog.py
from assemblix_api.external.avatar.avatar_catalog import (
    AVATAR_PROVIDER_LABELS,
    find_avatar_model,
    list_avatar_models,
    list_avatar_providers,
)


def test_anam_is_registered():
    assert AVATAR_PROVIDER_LABELS["anam"] == "Anam"


def test_list_providers_returns_anam():
    assert "anam" in list_avatar_providers()


def test_list_and_find_model():
    models = list_avatar_models("anam")
    assert models, "anam.json must declare at least one avatar model"
    first = models[0]
    assert find_avatar_model("anam", first.id) == first
    assert first.avatar_model  # non-empty provider avatar model id


def test_unknown_provider_is_empty():
    assert list_avatar_models("nope") == []
    assert find_avatar_model("nope", "x") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_avatar_catalog.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `base.py`**

```python
# assemblix_api/external/avatar/base.py
"""Metadata contract for the avatar-model registry (mirrors external/voice/base.py)."""

from __future__ import annotations

from assemblix_api.dto.base import DTOModel


class AvatarModelMetadata(DTOModel):
    """Static metadata for one avatar model, loaded from a provider JSON file."""

    id: str
    label: str
    description: str | None = None
    # Provider-native avatar model identifier passed back in personaConfig.avatarModel.
    avatar_model: str
    cost_per_minute: float | None = None
```

- [ ] **Step 4: Create `models/anam.json`**

```json
{
  "models": [
    {
      "id": "cara",
      "label": "Cara",
      "description": "Default anam avatar persona.",
      "avatar_model": "cara-4",
      "cost_per_minute": null
    }
  ]
}
```

- [ ] **Step 5: Create `avatar_catalog.py`**

```python
# assemblix_api/external/avatar/avatar_catalog.py
"""Data-driven avatar-model catalog (mirror of external/voice/voice_catalog.py).

Models are declared as data in models/<provider>.json. Adding a model to an
existing provider is a JSON edit; adding a provider also needs an
AVATAR_PROVIDER_LABELS entry.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from assemblix_api.external.avatar.base import AvatarModelMetadata

_AVATAR_MODELS_DIR = Path(__file__).parent / "models"

# Registered avatar providers -> display label. A provider without an entry here
# is invisible even if a JSON exists.
AVATAR_PROVIDER_LABELS: dict[str, str] = {"anam": "Anam"}


@cache
def _provider_models(provider: str) -> tuple[AvatarModelMetadata, ...]:
    path = _AVATAR_MODELS_DIR / f"{provider}.json"
    if not path.exists():
        return ()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return tuple(AvatarModelMetadata.model_validate(entry) for entry in data["models"])


def find_avatar_model(provider: str, model: str) -> AvatarModelMetadata | None:
    if provider not in AVATAR_PROVIDER_LABELS:
        return None
    return next((m for m in _provider_models(provider) if m.id == model), None)


def list_avatar_models(provider: str) -> list[AvatarModelMetadata]:
    if provider not in AVATAR_PROVIDER_LABELS:
        return []
    return list(_provider_models(provider))


def list_avatar_providers() -> list[str]:
    return [p for p in AVATAR_PROVIDER_LABELS if list_avatar_models(p)]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_avatar_catalog.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add assemblix_api/external/avatar/ tests/unit/test_avatar_catalog.py
git commit -m "feat(avatars): data-driven avatar model catalog (anam)"
```

---

## Task 3: anam adapter (`anam.py`)

**Files:**
- Create: `assemblix_api/external/avatar/anam.py`
- Test: `tests/unit/test_anam_adapter.py`

**Interfaces:**
- Consumes: `get_settings().anam_api_base_url` (added in Task 5).
- Produces:
  - `class AnamAvatar(BaseModel)`: `id: str`, `name: str`.
  - `async def list_avatars(api_key: str) -> list[AnamAvatar]` — `GET {base}/v1/avatars`.
  - `async def mint_session_token(*, api_key: str, persona_config: dict) -> str` — `POST {base}/v1/auth/session-token`, returns `sessionToken`.

- [ ] **Step 1: Write the failing test** (mock httpx at the transport seam)

```python
# tests/unit/test_anam_adapter.py
import httpx
import pytest

from assemblix_api.external.avatar import anam


@pytest.mark.asyncio
async def test_mint_session_token_posts_persona_and_returns_token(monkeypatch):
    captured = {}

    async def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["json"] = httpx.Request(request.method, request.url, content=request.content).content
        return httpx.Response(200, json={"sessionToken": "sess-123"})

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(anam, "_client", lambda: httpx.AsyncClient(transport=transport))

    token = await anam.mint_session_token(
        api_key="anam-key", persona_config={"name": "Cara", "llmId": "CUSTOMER_CLIENT_V1"}
    )

    assert token == "sess-123"
    assert captured["url"].endswith("/v1/auth/session-token")
    assert captured["auth"] == "Bearer anam-key"


@pytest.mark.asyncio
async def test_list_avatars_maps_items(monkeypatch):
    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "a1", "name": "Cara"}]})

    transport = httpx.MockTransport(_handler)
    monkeypatch.setattr(anam, "_client", lambda: httpx.AsyncClient(transport=transport))

    avatars = await anam.list_avatars("anam-key")

    assert [(a.id, a.name) for a in avatars] == [("a1", "Cara")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_anam_adapter.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `anam.py`**

```python
# assemblix_api/external/avatar/anam.py
"""Direct anam.ai client: avatar listing and session-token minting.

anam has its own API (not OpenAI-compatible). The session token lets the browser
SDK connect over WebRTC without exposing the API key. llmId=CUSTOMER_CLIENT_V1
disables anam's brain so the avatar only speaks text we push client-side.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from assemblix_api.core.settings import get_settings

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _base_url() -> str:
    return get_settings().anam_api_base_url.rstrip("/")


def _client() -> httpx.AsyncClient:
    """Factory kept as a seam so tests can inject a MockTransport."""
    return httpx.AsyncClient(timeout=_TIMEOUT)


class AnamAvatar(BaseModel):
    id: str
    name: str


async def list_avatars(api_key: str) -> list[AnamAvatar]:
    """Return the avatars available to ``api_key`` (GET /v1/avatars)."""
    async with _client() as client:
        resp = await client.get(
            f"{_base_url()}/v1/avatars", headers={"Authorization": f"Bearer {api_key}"}
        )
        resp.raise_for_status()
        data = resp.json()
    return [AnamAvatar(id=a["id"], name=a["name"]) for a in data.get("data", [])]


async def mint_session_token(*, api_key: str, persona_config: dict) -> str:
    """Exchange the API key for a short-lived client session token."""
    async with _client() as client:
        resp = await client.post(
            f"{_base_url()}/v1/auth/session-token",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"personaConfig": persona_config},
        )
        resp.raise_for_status()
        return resp.json()["sessionToken"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_anam_adapter.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/external/avatar/anam.py tests/unit/test_anam_adapter.py
git commit -m "feat(avatars): anam adapter (list_avatars + mint_session_token)"
```

---

## Task 4: Provider dispatch (`session.py`)

**Files:**
- Create: `assemblix_api/external/avatar/session.py`
- Test: `tests/unit/test_avatar_session_dispatch.py`

**Interfaces:**
- Consumes: `find_avatar_model`, `anam.mint_session_token`.
- Produces: `async def mint_session(*, provider: str, api_key: str, persona_config: dict) -> str` — dispatches by provider; raises `NotImplementedError` for unknown providers.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_avatar_session_dispatch.py
import pytest

from assemblix_api.external.avatar import session


@pytest.mark.asyncio
async def test_dispatch_anam(monkeypatch):
    async def _fake_mint(*, api_key, persona_config):
        return f"tok:{api_key}:{persona_config['name']}"

    monkeypatch.setattr(session.anam, "mint_session_token", _fake_mint)

    token = await session.mint_session(
        provider="anam", api_key="k", persona_config={"name": "Cara"}
    )
    assert token == "tok:k:Cara"


@pytest.mark.asyncio
async def test_dispatch_unknown_provider_raises():
    with pytest.raises(NotImplementedError):
        await session.mint_session(provider="nope", api_key="k", persona_config={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_avatar_session_dispatch.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `session.py`**

```python
# assemblix_api/external/avatar/session.py
"""Provider dispatch for minting an avatar session token.

Mirrors external/voice/synthesis.py: a thin ``if provider == ...`` seam rather
than a polymorphic base class, matching the existing voice layer. Adding a
provider = one branch here + one adapter module.
"""

from __future__ import annotations

from assemblix_api.external.avatar import anam


async def mint_session(*, provider: str, api_key: str, persona_config: dict) -> str:
    """Mint a client session token for ``provider`` with the given persona."""
    if provider == "anam":
        return await anam.mint_session_token(api_key=api_key, persona_config=persona_config)
    raise NotImplementedError(f"Avatar provider {provider!r} is not supported")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_avatar_session_dispatch.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/external/avatar/session.py tests/unit/test_avatar_session_dispatch.py
git commit -m "feat(avatars): provider dispatch for session minting"
```

---

## Task 5: Settings — `anam_api_base_url`

**Files:**
- Modify: `assemblix_api/core/settings.py` (after line 222, near the ElevenLabs settings)
- Modify: `.env.example` (document the var)
- Test: `tests/unit/test_avatar_settings.py`

**Interfaces:**
- Produces: `get_settings().anam_api_base_url` (default `https://api.anam.ai`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_avatar_settings.py
from assemblix_api.core.settings import get_settings


def test_anam_base_url_default():
    assert get_settings().anam_api_base_url == "https://api.anam.ai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_avatar_settings.py -v`
Expected: FAIL — `AttributeError: anam_api_base_url`.

- [ ] **Step 3: Add the setting**

```python
    # anam.ai (avatar output). BYO-key only this phase — no platform key. Override
    # the base URL to route through a proxy/gateway.
    anam_api_base_url: str = os.getenv("ANAM_API_BASE_URL", "https://api.anam.ai")
```

Add to `.env.example` under a new "AI avatars" comment block:

```bash
# --- AI avatars (anam.ai) — BYO key per project via credentials; base URL override only ---
ANAM_API_BASE_URL=https://api.anam.ai
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_avatar_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/core/settings.py .env.example tests/unit/test_avatar_settings.py
git commit -m "feat(avatars): anam_api_base_url setting"
```

---

## Task 6: `get_avatar_api_key_with_fallback` (BYO-only)

**Files:**
- Modify: `assemblix_api/services/credentials_service.py` (after `get_voice_api_key_with_fallback`, ~line 188)
- Test: `tests/integration/test_avatar_credentials.py`

**Interfaces:**
- Consumes: `CredentialsType.ANAM_TOKEN`, `self._check_ownership`, `self.get_decrypted_api_key`.
- Produces: `async def get_avatar_api_key_with_fallback(self, credentials_id, project_id, avatar_provider) -> str` — returns the decrypted BYO key; raises `HTTPException(400)` if the credential is missing/incompatible (no system fallback).

**Note:** BYO-only means the "fallback" name is kept for symmetry with voice but there is no system key — a missing/incompatible credential is a hard 400, not a fall-through.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_avatar_credentials.py
import pytest
from fastapi import HTTPException

from assemblix_api.database.models.credentials import CredentialsType


@pytest.mark.asyncio
async def test_resolves_byo_anam_key(credentials_service, project, make_credential):
    cred = await make_credential(
        project_id=project.id, type=CredentialsType.ANAM_TOKEN, value="anam-secret"
    )
    key = await credentials_service.get_avatar_api_key_with_fallback(
        credentials_id=cred.id, project_id=project.id, avatar_provider="anam"
    )
    assert key == "anam-secret"


@pytest.mark.asyncio
async def test_missing_credential_raises_400(credentials_service, project):
    with pytest.raises(HTTPException) as exc:
        await credentials_service.get_avatar_api_key_with_fallback(
            credentials_id=None, project_id=project.id, avatar_provider="anam"
        )
    assert exc.value.status_code == 400
```

> Fixtures `credentials_service`, `project`, `make_credential` follow the existing
> credentials integration tests (`tests/integration/test_credentials_crud.py`); reuse
> their factory. If `make_credential` does not exist, create the credential via
> `credentials_service.create(...)` as that file does.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_avatar_credentials.py -v`
Expected: FAIL — method does not exist.

- [ ] **Step 3: Implement the method**

```python
    _AVATAR_PROVIDER_TO_CREDENTIALS_TYPE = {"anam": CredentialsType.ANAM_TOKEN}

    async def get_avatar_api_key_with_fallback(
        self,
        credentials_id: UUID | None,
        project_id: UUID,
        avatar_provider: str,
    ) -> str:
        """Resolve an avatar-provider API key. BYO-only: no system key.

        A missing, unowned, or incompatible credential is a hard 400 (unlike the
        voice resolver, avatars have no system-key fallback this phase).
        """
        expected = self._AVATAR_PROVIDER_TO_CREDENTIALS_TYPE.get(avatar_provider)
        if expected is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown avatar provider {avatar_provider!r}",
            )
        if not credentials_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An avatar provider credential is required for {avatar_provider}",
            )
        credentials = await self._check_ownership(credentials_id, project_id)
        if credentials.type != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credentials type is not compatible with avatar provider {avatar_provider}",
            )
        return await self.get_decrypted_api_key(credentials_id, project_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_avatar_credentials.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/services/credentials_service.py tests/integration/test_avatar_credentials.py
git commit -m "feat(avatars): BYO-only avatar API key resolver"
```

---

## Task 7: Schema — `WorkflowAvatarConfig` + `output_type` avatar

**Files:**
- Modify: `assemblix_api/schemas/node.py` (add `WorkflowAvatarConfig`; extend `AgentNodeConfig.output_type` at line 92)
- Modify: `assemblix_api/schemas/workflow.py` (typed accessor for `config["avatar"]`)
- Test: `tests/unit/test_workflow_avatar_config.py`

**Interfaces:**
- Produces:
  - `WorkflowAvatarConfig(provider: str, avatar_model: str, avatar_id: str | None, voice_id: str | None, credential_id: str | None)`
  - `AgentNodeConfig.output_type: Literal["text", "voice", "avatar"]`
  - `parse_avatar_config(config: dict) -> WorkflowAvatarConfig | None` in `schemas/workflow.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_workflow_avatar_config.py
from assemblix_api.schemas.node import AgentNodeConfig, WorkflowAvatarConfig
from assemblix_api.schemas.workflow import parse_avatar_config


def test_agent_output_type_accepts_avatar():
    cfg = AgentNodeConfig(
        provider="openai", model="gpt-4o", instructions=[], output_type="avatar"
    )
    assert cfg.output_type == "avatar"


def test_parse_avatar_config_from_workflow_config():
    parsed = parse_avatar_config(
        {"avatar": {"provider": "anam", "avatarModel": "cara-4", "credentialId": "c1"}}
    )
    assert parsed is not None
    assert parsed.provider == "anam"
    assert parsed.avatar_model == "cara-4"
    assert parsed.credential_id == "c1"


def test_parse_avatar_config_absent_returns_none():
    assert parse_avatar_config({}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_workflow_avatar_config.py -v`
Expected: FAIL — import errors.

- [ ] **Step 3: Add `WorkflowAvatarConfig` and extend `output_type`**

In `schemas/node.py`, after `VoiceOutputConfig` (line 31):

```python
class WorkflowAvatarConfig(DTOModel):
    """Workflow-global avatar persona. Set in the editor header, stored in
    ``workflow.config["avatar"]``. Avatars are BYO-key only (credential_id)."""

    provider: str
    avatar_model: str
    avatar_id: str | None = None
    voice_id: str | None = None
    credential_id: str | None = None
```

Change line 92:

```python
    output_type: Literal["text", "voice", "avatar"] = "text"
```

Update the comment above it to mention `"avatar"` streams text (reuse 2a) for a
workflow-level avatar; no per-node avatar config.

- [ ] **Step 4: Add `parse_avatar_config` to `schemas/workflow.py`**

```python
from assemblix_api.schemas.node import WorkflowAvatarConfig


def parse_avatar_config(config: dict) -> WorkflowAvatarConfig | None:
    """Parse the workflow-global avatar persona from ``workflow.config``, or None."""
    raw = (config or {}).get("avatar")
    if not raw:
        return None
    return WorkflowAvatarConfig.model_validate(raw)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_workflow_avatar_config.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add assemblix_api/schemas/node.py assemblix_api/schemas/workflow.py tests/unit/test_workflow_avatar_config.py
git commit -m "feat(avatars): workflow-global avatar config + avatar output_type"
```

---

## Task 8: `StreamDeltaEventData.avatar` flag + emit + sink threading

**Files:**
- Modify: `assemblix_api/schemas/debug_events.py:31-34` (add `avatar` field)
- Modify: `assemblix_api/execution/debug_event_manager.py:116-127` (`emit_stream_delta` param)
- Modify: `assemblix_api/execution/node_runner.py:66-74` (thread avatar into `_sink`)
- Test: `tests/unit/test_stream_delta_avatar_flag.py`

**Interfaces:**
- Consumes: `AgentNodeConfig.output_type` (Task 7); the node instance's `typed_config`.
- Produces:
  - `StreamDeltaEventData.avatar: bool = False`
  - `emit_stream_delta(..., avatar: bool = False)`
  - Deltas from a node whose `typed_config.output_type == "avatar"` carry `avatar=True`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_stream_delta_avatar_flag.py
import pytest

from assemblix_api.execution.debug_event_manager import DebugEventManager
from assemblix_api.schemas.debug_events import DebugEventType, StreamDeltaEventData


def test_stream_delta_data_has_avatar_default_false():
    data = StreamDeltaEventData(node_id="n1", step_number=1, delta="hi")
    assert data.avatar is False


@pytest.mark.asyncio
async def test_emit_stream_delta_sets_avatar_flag():
    mgr = DebugEventManager()
    execution_id = __import__("uuid").uuid4()
    mgr.open_buffer(execution_id)

    await mgr.emit_stream_delta(
        execution_id, step_number=1, node_id="n1", delta="hi", avatar=True
    )

    events = [e async for e in mgr.subscribe(execution_id, after_seq=0)]
    delta_events = [e for e in events if e.event_type == DebugEventType.STREAM_DELTA]
    assert delta_events and delta_events[0].data["avatar"] is True
```

> If iterating `subscribe` blocks waiting for a terminal event, follow the pattern
> in `tests/unit/test_debug_event_manager_stream.py` (emit a terminal event or use
> the buffer's direct read). Match whatever that existing test does.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stream_delta_avatar_flag.py -v`
Expected: FAIL — `avatar` unknown.

- [ ] **Step 3: Add the field**

`schemas/debug_events.py`:

```python
class StreamDeltaEventData(DTOModel):
    node_id: str
    step_number: int
    delta: str
    # True when the delta comes from an agent node with output_type=="avatar";
    # the client forwards only these into the avatar SDK's streamMessageChunk.
    avatar: bool = False
```

- [ ] **Step 4: Thread through `emit_stream_delta`**

`debug_event_manager.py`:

```python
    async def emit_stream_delta(
        self,
        execution_id: UUID,
        *,
        step_number: int,
        node_id: str,
        delta: str,
        avatar: bool = False,
    ) -> None:
        """Emit a text-delta event from a streaming agent node."""
        event_data = StreamDeltaEventData(
            node_id=node_id, step_number=step_number, delta=delta, avatar=avatar
        )
        event = DebugEvent(
            event_type=DebugEventType.STREAM_DELTA,
            execution_id=execution_id,
            timestamp=datetime.now(),
            data=event_data.model_dump(),
        )
        await self.emit_event(execution_id, event)
```

- [ ] **Step 5: Thread avatar-ness into the sink**

`node_runner.py`, inside `run`, replace the `_sink` block:

```python
            execution_id = ctx.execution_id
            is_avatar = getattr(getattr(node, "typed_config", None), "output_type", None) == "avatar"

            async def _sink(text: str) -> None:
                await self._debug_event_manager.emit_stream_delta(
                    execution_id,
                    step_number=step_number,
                    node_id=node_id,
                    delta=text,
                    avatar=is_avatar,
                )

            node_input.on_delta = _sink
```

> `typed_config` is a property on the agent node; non-agent nodes lack it, so the
> `getattr` chain yields `None` → `is_avatar=False`. If `typed_config` raises on a
> node with invalid config, that failure already surfaces in `node.execute`; guard
> only if a test shows a regression.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_stream_delta_avatar_flag.py tests/unit/test_debug_event_manager_stream.py -v`
Expected: PASS (new + existing unchanged).

- [ ] **Step 7: Commit**

```bash
git add assemblix_api/schemas/debug_events.py assemblix_api/execution/debug_event_manager.py assemblix_api/execution/node_runner.py tests/unit/test_stream_delta_avatar_flag.py
git commit -m "feat(avatars): tag avatar-node stream deltas for client forwarding"
```

---

## Task 9: Discovery + session DTOs (`dto/responses/avatar.py`)

**Files:**
- Create: `assemblix_api/dto/responses/avatar.py`
- Test: covered by Task 10's router tests (no standalone test — pure DTOs).

**Interfaces:**
- Produces:
  - `AvatarProviderListItem(name, label, models_count)`
  - `AvatarListItem(id, name)`
  - `AvatarSessionResponse(provider, session_token, video_config: dict)`

- [ ] **Step 1: Create the DTOs**

```python
# assemblix_api/dto/responses/avatar.py
"""Response DTOs for the /api/avatar discovery + session endpoints."""

from __future__ import annotations

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class AvatarProviderListItem(DTOModel):
    name: str = Field(description="Stable provider id, e.g. 'anam'.")
    label: str = Field(description="Human-readable provider name.")
    models_count: int


class AvatarListItem(DTOModel):
    id: str
    name: str


class AvatarSessionResponse(DTOModel):
    """Everything the client SDK needs to connect; the API key never appears here."""

    provider: str
    session_token: str
    # Provider-specific hints the client passes to createClient (e.g. avatarModel).
    video_config: dict
```

- [ ] **Step 2: Type-check**

Run: `mypy assemblix_api/dto/responses/avatar.py`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add assemblix_api/dto/responses/avatar.py
git commit -m "feat(avatars): discovery + session response DTOs"
```

---

## Task 10: Avatar service + router (`avatar_service.py`, `api/rest/avatar.py`)

**Files:**
- Create: `assemblix_api/services/avatar_service.py`
- Create: `assemblix_api/api/rest/avatar.py`
- Modify: `assemblix_api/dependencies.py` (add `get_avatar_service`)
- Modify: router registration (where `voice.router` is included — grep `include_router` for `voice`)
- Test: `tests/integration/test_avatar_endpoints.py`

**Interfaces:**
- Consumes: `credentials_service.get_avatar_api_key_with_fallback`, `session.mint_session`, `parse_avatar_config`, `workflow_service` (load workflow), `anam.list_avatars`.
- Produces:
  - `GET /api/avatar/providers` → `list[AvatarProviderListItem]`
  - `GET /api/avatar/providers/{provider}/models` → `list[AvatarModelMetadata]`
  - `GET /api/avatar/credentials/{credentials_id}/avatars` → `list[AvatarListItem]`
  - `POST /api/workflows/{workflow_id}/avatar/session` → `AvatarSessionResponse`
  - `AvatarService.mint_workflow_session(workflow_id, user) -> AvatarSessionResponse`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_avatar_endpoints.py
import pytest

from assemblix_api.database.models.credentials import CredentialsType


@pytest.mark.asyncio
async def test_list_providers(client, auth_headers):
    resp = await client.get("/api/avatar/providers", headers=auth_headers)
    assert resp.status_code == 200
    assert any(p["name"] == "anam" for p in resp.json())


@pytest.mark.asyncio
async def test_list_credential_avatars(client, auth_headers, mocker, make_credential, project):
    cred = await make_credential(
        project_id=project.id, type=CredentialsType.ANAM_TOKEN, value="anam-key"
    )

    async def _fake(api_key):
        assert api_key == "anam-key"
        from assemblix_api.external.avatar.anam import AnamAvatar
        return [AnamAvatar(id="a1", name="Cara")]

    mocker.patch("assemblix_api.api.rest.avatar.list_avatars", side_effect=_fake)

    resp = await client.get(f"/api/avatar/credentials/{cred.id}/avatars", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == [{"id": "a1", "name": "Cara"}]


@pytest.mark.asyncio
async def test_mint_workflow_session(client, auth_headers, mocker, make_credential, project, make_workflow):
    cred = await make_credential(
        project_id=project.id, type=CredentialsType.ANAM_TOKEN, value="anam-key"
    )
    wf = await make_workflow(
        project_id=project.id,
        config={"avatar": {"provider": "anam", "avatarModel": "cara-4", "credentialId": str(cred.id)}},
    )

    mocker.patch(
        "assemblix_api.services.avatar_service.mint_session",
        side_effect=lambda **kw: _return("sess-xyz"),
    )

    resp = await client.post(f"/api/workflows/{wf.id}/avatar/session", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "anam"
    assert body["sessionToken"] == "sess-xyz"


async def _return(v):
    return v


@pytest.mark.asyncio
async def test_mint_session_400_when_no_avatar_config(client, auth_headers, make_workflow, project):
    wf = await make_workflow(project_id=project.id, config={})
    resp = await client.post(f"/api/workflows/{wf.id}/avatar/session", headers=auth_headers)
    assert resp.status_code == 400
```

> Reuse existing fixtures (`client`, `auth_headers`, `project`, `make_credential`,
> `make_workflow`) from `tests/integration/` conftest. If `make_workflow` accepting
> `config=` doesn't exist, extend the existing workflow factory to pass `config`
> through (it maps straight to the JSONB column).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_avatar_endpoints.py -v`
Expected: FAIL — routes 404.

- [ ] **Step 3: Implement `avatar_service.py`**

```python
# assemblix_api/services/avatar_service.py
"""Avatar session orchestration: build the persona from the workflow-global
avatar config, resolve the BYO key, and mint a provider session token."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from assemblix_api.database.models.user import User
from assemblix_api.dto.responses.avatar import AvatarSessionResponse
from assemblix_api.external.avatar.session import mint_session
from assemblix_api.schemas.workflow import parse_avatar_config
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.project_service import ProjectService
from assemblix_api.services.workflow_service import WorkflowService

_CUSTOMER_LLM_ID = "CUSTOMER_CLIENT_V1"  # disables anam's brain; we push text


class AvatarService:
    def __init__(
        self,
        workflow_service: WorkflowService,
        credentials_service: CredentialsService,
        project_service: ProjectService,
    ) -> None:
        self._workflows = workflow_service
        self._credentials = credentials_service
        self._projects = project_service

    async def mint_workflow_session(
        self, workflow_id: UUID, user: User
    ) -> AvatarSessionResponse:
        workflow = await self._workflows.get_by_id(workflow_id)
        await self._projects.verify_user_project_access(user, workflow.project_id)

        avatar = parse_avatar_config(workflow.config or {})
        if avatar is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This workflow has no avatar configured",
            )

        api_key = await self._credentials.get_avatar_api_key_with_fallback(
            credentials_id=UUID(avatar.credential_id) if avatar.credential_id else None,
            project_id=workflow.project_id,
            avatar_provider=avatar.provider,
        )

        persona_config = {
            "name": "Assemblix",
            "avatarId": avatar.avatar_id,
            "avatarModel": avatar.avatar_model,
            "voiceId": avatar.voice_id,
            "llmId": _CUSTOMER_LLM_ID,
        }
        persona_config = {k: v for k, v in persona_config.items() if v is not None}

        session_token = await mint_session(
            provider=avatar.provider, api_key=api_key, persona_config=persona_config
        )
        return AvatarSessionResponse(
            provider=avatar.provider,
            session_token=session_token,
            video_config={"avatarModel": avatar.avatar_model},
        )
```

- [ ] **Step 4: Implement `api/rest/avatar.py`**

```python
# assemblix_api/api/rest/avatar.py
"""Avatar provider/model discovery + workflow session-token minting.

Mirror of api/rest/voice.py. Discovery powers the editor-header avatar picker;
the session route hands the browser SDK a short-lived token (key never exposed).
Avatars are BYO-key only — there is no system-avatars endpoint.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_avatar_service,
    get_credentials_service,
    get_current_user,
    get_project_service,
)
from assemblix_api.dto.responses.avatar import (
    AvatarListItem,
    AvatarProviderListItem,
    AvatarSessionResponse,
)
from assemblix_api.external.avatar.anam import list_avatars
from assemblix_api.external.avatar.avatar_catalog import (
    AVATAR_PROVIDER_LABELS,
    list_avatar_models,
    list_avatar_providers,
)
from assemblix_api.external.avatar.base import AvatarModelMetadata
from assemblix_api.services.avatar_service import AvatarService
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.project_service import ProjectService

router = APIRouter(tags=["Avatar"])


@router.get("/avatar/providers", response_model=list[AvatarProviderListItem])
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> list[AvatarProviderListItem]:
    return [
        AvatarProviderListItem(
            name=name,
            label=AVATAR_PROVIDER_LABELS[name],
            models_count=len(list_avatar_models(name)),
        )
        for name in list_avatar_providers()
    ]


@router.get("/avatar/providers/{provider_name}/models", response_model=list[AvatarModelMetadata])
async def list_provider_models(
    provider_name: str,
    current_user: User = Depends(get_current_user),
) -> list[AvatarModelMetadata]:
    if provider_name not in AVATAR_PROVIDER_LABELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Avatar provider {provider_name!r} is not registered",
        )
    return list_avatar_models(provider_name)


@router.get("/avatar/credentials/{credentials_id}/avatars", response_model=list[AvatarListItem])
async def list_credential_avatars(
    credentials_id: UUID,
    current_user: User = Depends(get_current_user),
    credentials_service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
) -> list[AvatarListItem]:
    credentials = await credentials_service.get_by_id(credentials_id)
    await project_service.verify_user_project_access(current_user, credentials.project_id)
    if credentials.type != CredentialsType.ANAM_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This credential is not an anam token",
        )
    api_key = await credentials_service.get_decrypted_api_key(
        credentials_id, credentials.project_id
    )
    avatars = await list_avatars(api_key)
    return [AvatarListItem(id=a.id, name=a.name) for a in avatars]


@router.post("/workflows/{workflow_id}/avatar/session", response_model=AvatarSessionResponse)
async def mint_avatar_session(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    avatar_service: AvatarService = Depends(get_avatar_service),
) -> AvatarSessionResponse:
    return await avatar_service.mint_workflow_session(workflow_id, current_user)
```

- [ ] **Step 5: Wire dependencies + mount the router**

In `dependencies.py`, add (mirroring `get_credentials_service`):

```python
def get_avatar_service(
    workflow_service: WorkflowService = Depends(get_workflow_service),
    credentials_service: CredentialsService = Depends(get_credentials_service),
    project_service: ProjectService = Depends(get_project_service),
) -> AvatarService:
    return AvatarService(workflow_service, credentials_service, project_service)
```

Where `voice.router` is included (grep `include_router(voice`), add:

```python
from assemblix_api.api.rest import avatar
app.include_router(avatar.router, prefix="/api")
```

> Match the exact prefix used for the voice router. The avatar router paths above
> already include `/avatar/...` and `/workflows/...`, so it mounts under `/api`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/integration/test_avatar_endpoints.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Full backend gate**

Run: `make check` (ruff + mypy + pytest)
Expected: green.

- [ ] **Step 8: Commit**

```bash
git add assemblix_api/services/avatar_service.py assemblix_api/api/rest/avatar.py assemblix_api/dependencies.py tests/integration/test_avatar_endpoints.py
git commit -m "feat(avatars): discovery + workflow session-mint API"
```

---

## Task 11: Frontend — `avatar-model` RTK entity

**Files:**
- Create: `src/entities/avatar-model/api/avatar-model.api.ts`, `model/types.ts`, `index.ts`
- Modify: `src/shared/api/baseApi.ts` (add `"AvatarModels"` to `tagTypes`)

**Interfaces:**
- Produces hooks: `useGetAvatarProvidersQuery`, `useGetAvatarProviderModelsQuery`, `useGetCredentialAvatarsQuery`; types `AvatarProviderListItem`, `AvatarModelMetadata`, `AvatarListItem`, `WorkflowAvatarConfig`.

- [ ] **Step 1: Create `model/types.ts`**

```ts
export interface AvatarProviderListItem {
  name: string;
  label: string;
  modelsCount: number;
}

export interface AvatarModelMetadata {
  id: string;
  label: string;
  description?: string | null;
  avatarModel: string;
  costPerMinute?: number | null;
}

export interface AvatarListItem {
  id: string;
  name: string;
}

export interface AvatarSessionResponse {
  provider: string;
  sessionToken: string;
  videoConfig: Record<string, unknown>;
}

export interface WorkflowAvatarConfig {
  provider: string;
  avatarModel: string;
  avatarId?: string;
  voiceId?: string;
  credentialId?: string;
}
```

- [ ] **Step 2: Create `api/avatar-model.api.ts`**

```ts
import { baseApi } from "@/shared/api/baseApi";
import type {
  AvatarListItem,
  AvatarModelMetadata,
  AvatarProviderListItem,
} from "../model/types";

export const avatarModelApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getAvatarProviders: build.query<AvatarProviderListItem[], void>({
      query: () => ({ url: "/avatar/providers", method: "GET" }),
      providesTags: [{ type: "AvatarModels", id: "LIST" }],
    }),
    getAvatarProviderModels: build.query<AvatarModelMetadata[], { providerName: string }>({
      query: ({ providerName }) => ({
        url: `/avatar/providers/${providerName}/models`,
        method: "GET",
      }),
      providesTags: (_r, _e, { providerName }) => [
        { type: "AvatarModels", id: `models:${providerName}` },
      ],
    }),
    getCredentialAvatars: build.query<AvatarListItem[], { credentialId: string }>({
      query: ({ credentialId }) => ({
        url: `/avatar/credentials/${credentialId}/avatars`,
        method: "GET",
      }),
      providesTags: (_r, _e, { credentialId }) => [
        { type: "AvatarModels", id: `avatars:${credentialId}` },
      ],
    }),
  }),
});

export const {
  useGetAvatarProvidersQuery,
  useGetAvatarProviderModelsQuery,
  useGetCredentialAvatarsQuery,
} = avatarModelApi;
```

- [ ] **Step 3: Create `index.ts`**

```ts
export {
  useGetAvatarProviders Query,
  useGetAvatarProviderModelsQuery,
  useGetCredentialAvatarsQuery,
} from "./api/avatar-model.api";
export type {
  AvatarProviderListItem,
  AvatarModelMetadata,
  AvatarListItem,
  AvatarSessionResponse,
  WorkflowAvatarConfig,
} from "./model/types";
```

> Fix the typo: `useGetAvatarProvidersQuery` (no space) — written explicitly here as a reminder to keep hook names exact.

- [ ] **Step 4: Register the cache tag**

In `src/shared/api/baseApi.ts`, add `"AvatarModels"` to the `tagTypes` array (next to `"VoiceModels"`).

- [ ] **Step 5: Type-check**

Run: `npm run build`
Expected: no type errors.

- [ ] **Step 6: Commit**

```bash
git add src/entities/avatar-model/ src/shared/api/baseApi.ts
git commit -m "feat(avatars): avatar-model RTK entity"
```

---

## Task 12: Frontend — anam credential mapping + config types

**Files:**
- Modify: `src/entities/credential/lib/provider-credential-type.ts` (add anam → credential type)
- Modify: `src/entities/credential` credential-type enum/const (wherever `elevenlabs` credential type is declared)
- Modify: `src/entities/workflow/model/types.ts` (`output_type` union += `"avatar"`; re-export `WorkflowAvatarConfig`; add `avatar?` to workflow config type)

**Interfaces:**
- Consumes: `WorkflowAvatarConfig` (Task 11).
- Produces: `getCredentialTypeForProvider("anam")` returns the anam credential type; `AgentNodeConfig.outputType` includes `"avatar"`.

- [ ] **Step 1: Add the anam credential type**

Locate where `elevenlabs` maps to a `CredentialType` (frontend enum) in
`entities/credential`. Add an `ANAM` member (value `"anam_token"`, matching the
backend enum) and map it in `PROVIDER_TO_CREDENTIAL_TYPE`:

```ts
// provider-credential-type.ts
[ "anam" ]: CredentialType.ANAM,
```

- [ ] **Step 2: Extend workflow types**

In `entities/workflow/model/types.ts`:

```ts
export interface WorkflowAvatarConfig {
  provider: string;
  avatarModel: string;
  avatarId?: string;
  voiceId?: string;
  credentialId?: string;
}
```

Change `AgentNodeConfig.outputType`:

```ts
  outputType?: "text" | "voice" | "avatar";
```

Add to the workflow config type (wherever `WorkflowDefinition.config` / editor config lives):

```ts
  avatar?: WorkflowAvatarConfig;
```

- [ ] **Step 3: Type-check**

Run: `npm run build`
Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git add src/entities/credential/ src/entities/workflow/model/types.ts
git commit -m "feat(avatars): anam credential mapping + avatar config types"
```

---

## Task 13: Frontend — `AvatarOutputPicker` + editor-header config

**Files:**
- Create: `.../node-forms/avatar-output-picker.tsx`
- Modify: workflow editor header component (add an "AI avatar" config entry that opens the picker and writes `workflow.config.avatar`)
- Modify: `.../node-forms/agent-node-form.tsx` (third `outputType` option + yellow warning)

**Interfaces:**
- Consumes: `useGetAvatarProvidersQuery`, `useGetAvatarProviderModelsQuery`, `useGetCredentialAvatarsQuery`, `CredentialSelect`, `WorkflowAvatarConfig`.
- Produces: `<AvatarOutputPicker value onChange />`; agent node `outputType: "avatar"` selectable.

- [ ] **Step 1: Build `AvatarOutputPicker`**

Clone `voice-output-picker.tsx` structure (provider → credential → model/avatar cascade), swapping the queries and removing the system-key branch (BYO-only). Concrete shape:

```tsx
// avatar-output-picker.tsx
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { CredentialSelect } from "@/entities/credential";
import { getCredentialTypeForProvider } from "@/entities/credential";
import {
  useGetAvatarProvidersQuery,
  useGetAvatarProviderModelsQuery,
  useGetCredentialAvatarsQuery,
  type WorkflowAvatarConfig,
} from "@/entities/avatar-model";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/shared/ui/select";

interface Props {
  value: WorkflowAvatarConfig | undefined;
  onChange: (next: WorkflowAvatarConfig) => void;
}

export const AvatarOutputPicker = ({ value, onChange }: Props) => {
  const { t } = useTranslation();
  const { data: providers } = useGetAvatarProvidersQuery();
  const provider = value?.provider;
  const { data: models } = useGetAvatarProviderModelsQuery(
    provider ? { providerName: provider } : ({} as { providerName: string }),
    { skip: !provider },
  );
  const { data: avatars } = useGetCredentialAvatarsQuery(
    value?.credentialId ? { credentialId: value.credentialId } : ({} as { credentialId: string }),
    { skip: !value?.credentialId },
  );

  const credentialType = useMemo(
    () => (provider ? getCredentialTypeForProvider(provider) : undefined),
    [provider],
  );

  const patch = (p: Partial<WorkflowAvatarConfig>) =>
    onChange({ provider: "", avatarModel: "", ...value, ...p });

  return (
    <div className="flex flex-col gap-3">
      {/* provider */}
      <Select value={provider} onValueChange={(v) => patch({ provider: v, avatarModel: "" })}>
        <SelectTrigger><SelectValue placeholder={t("nodeForms.avatar.selectProvider")} /></SelectTrigger>
        <SelectContent>
          {providers?.map((p) => <SelectItem key={p.name} value={p.name}>{p.label}</SelectItem>)}
        </SelectContent>
      </Select>

      {/* credential (BYO required) */}
      {credentialType && (
        <CredentialSelect
          type={credentialType}
          value={value?.credentialId}
          onChange={(id) => patch({ credentialId: id })}
        />
      )}

      {/* avatar model */}
      {provider && (
        <Select value={value?.avatarModel} onValueChange={(v) => patch({ avatarModel: v })}>
          <SelectTrigger><SelectValue placeholder={t("nodeForms.avatar.selectModel")} /></SelectTrigger>
          <SelectContent>
            {models?.map((m) => <SelectItem key={m.id} value={m.avatarModel}>{m.label}</SelectItem>)}
          </SelectContent>
        </Select>
      )}

      {/* avatar id from the account (optional refinement) */}
      {avatars && avatars.length > 0 && (
        <Select value={value?.avatarId} onValueChange={(v) => patch({ avatarId: v })}>
          <SelectTrigger><SelectValue placeholder={t("nodeForms.avatar.selectAvatar")} /></SelectTrigger>
          <SelectContent>
            {avatars.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
          </SelectContent>
        </Select>
      )}
    </div>
  );
};
```

> Match the exact `Select`/`CredentialSelect` import paths and prop names used by
> `voice-output-picker.tsx`; adjust if they differ. Keep the cascade behavior identical.

- [ ] **Step 2: Add the editor-header entry**

In the workflow editor header, add a control (button/popover) "AI avatar" that renders
`<AvatarOutputPicker value={workflow.config.avatar} onChange={saveAvatarConfig} />`, where
`saveAvatarConfig` writes `config.avatar` through the existing workflow-config update path
(the same one that persists other `config` fields). Follow how the header persists existing
settings.

- [ ] **Step 3: Agent node form — third option + warning**

In `agent-node-form.tsx`, extend the output-type `Select` (currently text/voice) with an
avatar option, and show a warning when avatar is chosen but the workflow has no avatar config:

```tsx
<SelectItem value="avatar">{t("nodeForms.agent.outputTypeAvatar")}</SelectItem>
```

```tsx
{formData.outputType === "avatar" && !workflowHasAvatarConfig && (
  <p className="text-amber-600 text-sm">{t("nodeForms.agent.avatarNotConfigured")}</p>
)}
```

Where `workflowHasAvatarConfig = Boolean(workflow.config?.avatar?.avatarModel)`. When
`outputType === "avatar"`, do NOT render a per-node picker (avatar config is workflow-global)
— unlike the `"voice"` branch which renders `VoiceOutputPicker`.

- [ ] **Step 4: Type-check**

Run: `npm run build`
Expected: no type errors.

- [ ] **Step 5: Commit**

```bash
git add src/entities/workflow/lib/workflow-editor/
git commit -m "feat(avatars): avatar picker in header + agent-node avatar output option"
```

---

## Task 14: Frontend — `AvatarRenderer` interface + `AnamRenderer`

**Files:**
- Create: `.../workflow-editor/lib/avatar-renderer/types.ts`, `anam-renderer.ts`, `index.ts`
- Dependency: `npm install @anam-ai/js-sdk`

**Interfaces:**
- Produces:
  - `interface AvatarRenderer { connect(sessionToken, videoEl): Promise<void>; speak(): { chunk(text: string): void; end(): void }; disconnect(): void }`
  - `createAnamRenderer(): AvatarRenderer`
  - `createRenderer(provider: string): AvatarRenderer` (selects by provider).

- [ ] **Step 1: Install the SDK**

Run: `npm install @anam-ai/js-sdk`
Expected: added to `package.json` dependencies.

- [ ] **Step 2: Define the interface (`types.ts`)**

```ts
export interface AvatarTalkStream {
  chunk(text: string): void;
  end(): void;
}

export interface AvatarRenderer {
  connect(sessionToken: string, videoEl: HTMLVideoElement): Promise<void>;
  speak(): AvatarTalkStream;
  disconnect(): void;
}
```

- [ ] **Step 3: Implement `AnamRenderer`**

```ts
// anam-renderer.ts
import { createClient, type AnamClient } from "@anam-ai/js-sdk";
import type { AvatarRenderer, AvatarTalkStream } from "./types";

export const createAnamRenderer = (): AvatarRenderer => {
  let client: AnamClient | null = null;

  return {
    async connect(sessionToken, videoEl) {
      client = createClient(sessionToken);
      videoEl.id = videoEl.id || "anam-avatar-video";
      await client.streamToVideoElement(videoEl.id);
    },
    speak(): AvatarTalkStream {
      if (!client) throw new Error("Anam renderer not connected");
      const stream = client.createTalkMessageStream();
      return {
        chunk: (text) => stream.streamMessageChunk(text, false),
        end: () => stream.endMessage(),
      };
    },
    disconnect() {
      client?.stopStreaming();
      client = null;
    },
  };
};
```

> Verify the exact `@anam-ai/js-sdk` export names (`createClient`, `streamToVideoElement`,
> `createTalkMessageStream`, `streamMessageChunk`, `endMessage`, `stopStreaming`) against
> the installed package's types; adjust if the published API differs. The spec's method
> names come from anam's docs.

- [ ] **Step 4: Provider selector (`index.ts`)**

```ts
import { createAnamRenderer } from "./anam-renderer";
import type { AvatarRenderer } from "./types";

export type { AvatarRenderer, AvatarTalkStream } from "./types";

export const createRenderer = (provider: string): AvatarRenderer => {
  if (provider === "anam") return createAnamRenderer();
  throw new Error(`Unsupported avatar provider: ${provider}`);
};
```

- [ ] **Step 5: Type-check**

Run: `npm run build`
Expected: no type errors.

- [ ] **Step 6: Commit**

```bash
git add package.json package-lock.json src/entities/workflow/lib/workflow-editor/lib/avatar-renderer/
git commit -m "feat(avatars): AvatarRenderer interface + AnamRenderer"
```

---

## Task 15: Frontend — `use-avatar-session` + conversational wiring

**Files:**
- Create: `.../workflow-editor/lib/use-avatar-session.ts`
- Modify: the chat/run surface (add the avatar mode that mints, connects, and forwards deltas)
- Modify: `.../lib/use-workflow-debug.ts` (expose an `onStreamDelta` callback carrying the `avatar` flag, or a per-delta subscription the avatar hook can consume)

**Interfaces:**
- Consumes: `createRenderer`, `AvatarSessionResponse`, the existing debug/execute streaming (`STREAM_DELTA` with `avatar: boolean`).
- Produces: `useAvatarSession(workflowId)` → `{ videoRef, connect, disconnect, isConnected }`, wired so avatar-flagged deltas call `talkStream.chunk(...)` and node end calls `talkStream.end()`.

- [ ] **Step 1: Mint helper (RTK mutation)**

Add to `avatar-model.api.ts` a mutation:

```ts
mintAvatarSession: build.mutation<AvatarSessionResponse, { workflowId: string }>({
  query: ({ workflowId }) => ({
    url: `/workflows/${workflowId}/avatar/session`,
    method: "POST",
  }),
}),
```

Export `useMintAvatarSessionMutation`. Import `AvatarSessionResponse` type.

- [ ] **Step 2: Implement `use-avatar-session.ts`**

```ts
import { useCallback, useRef, useState } from "react";
import { useMintAvatarSessionMutation } from "@/entities/avatar-model";
import { createRenderer, type AvatarRenderer, type AvatarTalkStream } from "./avatar-renderer";

export const useAvatarSession = (workflowId: string) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rendererRef = useRef<AvatarRenderer | null>(null);
  const talkRef = useRef<AvatarTalkStream | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [mint] = useMintAvatarSessionMutation();

  const connect = useCallback(async () => {
    if (!videoRef.current) return;
    const session = await mint({ workflowId }).unwrap();
    const renderer = createRenderer(session.provider);
    await renderer.connect(session.sessionToken, videoRef.current);
    rendererRef.current = renderer;
    setIsConnected(true);
  }, [mint, workflowId]);

  // Called for each STREAM_DELTA event by the run consumer.
  const onDelta = useCallback((delta: { avatar: boolean; delta: string }) => {
    if (!delta.avatar || !rendererRef.current) return;
    if (!talkRef.current) talkRef.current = rendererRef.current.speak();
    talkRef.current.chunk(delta.delta);
  }, []);

  // Called when the avatar node's step completes.
  const onAvatarNodeComplete = useCallback(() => {
    talkRef.current?.end();
    talkRef.current = null;
  }, []);

  const disconnect = useCallback(() => {
    rendererRef.current?.disconnect();
    rendererRef.current = null;
    talkRef.current = null;
    setIsConnected(false);
  }, []);

  return { videoRef, connect, disconnect, isConnected, onDelta, onAvatarNodeComplete };
};
```

- [ ] **Step 3: Wire into the run/chat surface**

In the conversational surface that runs the workflow with streaming (reuse
`use-workflow-debug.ts`'s `stream=true` audio path — the user speaks, audio is POSTed to
`/execute/debug/audio`), route each `STREAM_DELTA` event to `onDelta({ avatar, delta })` and
each avatar-node `STEP_COMPLETE` to `onAvatarNodeComplete()`. Render `<video ref={videoRef} autoPlay playsInline />` when the workflow has `config.avatar`. Call `connect()` on mount of
the avatar mode and `disconnect()` on unmount.

> `use-workflow-debug.ts` already parses `audio_delta`; add a `stream_delta` branch (if not
> present) that forwards `{ avatar: eventData.data.avatar, delta: eventData.data.delta }` to a
> caller-supplied callback. Keep existing text-delta rendering intact.

- [ ] **Step 4: Type-check + manual dogfood**

Run: `npm run build`
Expected: no type errors.

Manual dogfood (needs a real anam BYO key + running stack): configure a workflow avatar,
open the avatar mode, speak, confirm the avatar lip-syncs the agent's streamed reply.

- [ ] **Step 5: Commit**

```bash
git add src/entities/avatar-model/ src/entities/workflow/lib/workflow-editor/
git commit -m "feat(avatars): avatar session hook + conversational wiring"
```

---

## Task 16: Frontend — i18n keys (en/es/ru)

**Files:**
- Modify: `src/shared/i18n/locales/{en,es,ru}.json`

**Interfaces:**
- Produces: `nodeForms.agent.outputTypeAvatar`, `nodeForms.agent.avatarNotConfigured`, and a `nodeForms.avatar.*` block (`selectProvider`, `selectModel`, `selectAvatar`, plus header labels).

- [ ] **Step 1: Add keys to all three locales**

en (mirror the tone of the existing `nodeForms.agent`/`nodeForms.end` voice keys):

```json
"agent": {
  "outputTypeAvatar": "AI avatar",
  "avatarNotConfigured": "This workflow has no avatar configured. Set one in the workflow header."
},
"avatar": {
  "title": "AI avatar",
  "selectProvider": "Select avatar provider",
  "selectModel": "Select avatar model",
  "selectAvatar": "Select avatar",
  "credential": "Avatar provider credential"
}
```

Provide ru and es translations of the same keys (translate the values; keep keys identical).

- [ ] **Step 2: Type-check / build**

Run: `npm run build`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add src/shared/i18n/locales/
git commit -m "feat(avatars): i18n keys for avatar output (en/es/ru)"
```

---

## Self-Review

**Spec coverage:**
- API-first three contracts → Tasks 9/10 (mint + discovery), Task 8 (tagged deltas over the existing SSE), Task 15 (client consumes turn+stream). ✅
- Backend `external/avatar/*` mirror → Tasks 2–4. ✅
- Credentials BYO-only + `ANAM_TOKEN` → Tasks 1, 6. ✅
- Settings → Task 5. ✅
- `config.avatar` + `output_type` avatar + warning → Tasks 7, 13. ✅
- Two-sided multi-provider (backend dispatch + client `AvatarRenderer`) → Tasks 4, 14. ✅
- Our STT / audio turn reuse → Task 15 (reuses `/execute/debug/audio`). ✅
- Frontend entity/picker/renderer/i18n → Tasks 11–16. ✅
- Out of scope (npm package, second provider, provider STT, metering) → not planned. ✅

**Placeholder scan:** No "TBD"/"similar to Task N". A few tasks reference matching existing
patterns (voice picker prop names, editor-header persistence path, anam SDK export names) —
these are verification instructions, not placeholders, because the concrete code is given and
the reference file is named. Fix the deliberate typo callout in Task 11 Step 3 when writing
the file (`useGetAvatarProvidersQuery`).

**Type consistency:** `AvatarModelMetadata.avatar_model` ↔ FE `avatarModel`; `WorkflowAvatarConfig`
fields identical across backend (Task 7) and frontend (Tasks 11/12); `emit_stream_delta(..., avatar=)`
↔ `StreamDeltaEventData.avatar` ↔ FE `onDelta({ avatar })` (Tasks 8/15); `mint_session(provider, api_key, persona_config)`
consistent across Tasks 3/4/10; hook names `useGetAvatar*` consistent across Tasks 11/13/15. ✅
