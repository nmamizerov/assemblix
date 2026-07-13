# Project API Key Scoping Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workflow/credentials/api-key CRUD endpoints enforce the API key's project scope, so an `sk_` key for project A can never read or write another project's data.

**Architecture:** Introduce an `AuthContext` (user + optional scoped project) resolved by a new `get_auth_context` dependency. Replace every `verify_user_project_access(current_user, project_id)` call in the three CRUD routers with a new `ProjectService.authorize_project_access(auth, project_id)` that additionally rejects any project_id ≠ the key's scope. JWT behaviour is unchanged (scope is `None`).

**Tech Stack:** Python 3.13, FastAPI, async SQLAlchemy, pytest (integration tests via httpx client + real Postgres).

## Global Constraints

- All code comments/docstrings in English.
- Comments only for non-trivial logic; minimal, no rationale-in-comments.
- Layering: no business logic in routers, no `HTTPException` in repositories, no SQLAlchemy in services, DTOs between layers.
- TDD: write the failing test first, then implementation.
- Activate `.venv` before any Python command (`source .venv/bin/activate`), run from `assemblix-app-api/`.
- Never hand-edit versions/CHANGELOG (release-please owns them).
- This is a **public** repo: never commit real secrets.

---

### Task 1: Repo bookkeeping for the separate `assemblix-aitools` repo

**Files:**
- Modify: `/.gitignore` (repo root)
- Modify: `/CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: nothing.
- Produces: an ignored path `/assemblix-aitools/` and documentation that it is a separate repo. No code depends on this task.

- [ ] **Step 1: Add the subfolder to root `.gitignore`**

Append to `/.gitignore` (after the existing `.claude/` block):

```gitignore

# Separate, independent repo developed in-tree (MCP server, skills, Claude Code plugins)
/assemblix-aitools/
```

- [ ] **Step 2: Document the boundary in root `CLAUDE.md`**

In `/CLAUDE.md`, under the "Monorepo layout" section's tree, add a line after the `internal-docs/` entry:

```
  assemblix-aitools/    — SEPARATE, independent git repo (gitignored here): MCP server + skills + Claude Code plugins
```

Then add this paragraph immediately after the blockquote that explains `docs/` vs `internal-docs/`:

```markdown
> **`assemblix-aitools/` is NOT part of this repo.** It is developed in-tree for
> convenience but is a **separate, independent git repository** (listed in this
> repo's `.gitignore`) with its own toolchain and its own license (MIT). It holds
> the standalone Assemblix MCP server (`assemblix-mcp` on PyPI) and, later, workflow
> authoring skills and Claude Code plugins. The core scoping that the MCP server
> relies on lives here in `assemblix-app-api`; everything client-side lives there.
```

- [ ] **Step 3: Verify the ignore works**

Run: `cd /Users/nmamizerov/Desktop/alfa/assemblix && mkdir -p assemblix-aitools && touch assemblix-aitools/.keep && git status --porcelain assemblix-aitools`
Expected: no output (the folder is ignored). Then `rm assemblix-aitools/.keep`.

- [ ] **Step 4: Commit**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix
git add .gitignore CLAUDE.md
git commit -m "chore: reserve and document assemblix-aitools as a separate repo"
```

---

### Task 2: `AuthContext` type + `resolve_context` service method

**Files:**
- Create: `assemblix-app-api/assemblix_api/core/auth_context.py`
- Modify: `assemblix-app-api/assemblix_api/services/api_key_service.py` (add `resolve_context`, refactor `verify_api_key` to delegate)
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py`

**Interfaces:**
- Consumes: existing `APIKeyService.get_api_key_object`, `self._api_keys.increment_usage`, `self._projects.get_by_id`, `self._organizations.get_by_id`, `self._users.get_by_id`.
- Produces:
  - `AuthContext(user: User, scoped_project_id: UUID | None)` — frozen dataclass in `core/auth_context.py`.
  - `APIKeyService.resolve_context(plain_key: str) -> tuple[User, APIKey] | None` — returns `(owner_user, api_key)` for a valid active key, else `None`; increments usage as a side effect.
  - `APIKeyService.verify_api_key` keeps its current signature `(plain_key: str) -> User | None`.

- [ ] **Step 1: Write the failing test**

Create `assemblix-app-api/tests/integration/test_api_key_scoping.py`:

```python
"""API-key project-scope enforcement across CRUD routers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest_asyncio

from assemblix_api.core.auth_context import AuthContext


@pytest_asyncio.fixture
async def second_project(client, auth_headers) -> str:
    """A second project in the SAME organization as auth_user's default project."""
    resp = await client.post(
        "/api/projects/",
        json={"name": "Second Project"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_resolve_context_returns_user_and_key(db_session: Any, api_key) -> None:
    # Arrange
    from assemblix_api.database.repositories.api_key_repository import APIKeyRepository
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )
    from assemblix_api.database.repositories.project_repository import ProjectRepository
    from assemblix_api.database.repositories.user_repository import UserRepository
    from assemblix_api.services.api_key_service import APIKeyService

    service = APIKeyService(
        APIKeyRepository(db_session),
        UserRepository(db_session),
        ProjectRepository(db_session),
        OrganizationRepository(db_session),
    )

    # Act
    ctx = await service.resolve_context(api_key.plain)

    # Assert
    assert ctx is not None
    user, key = ctx
    assert key.id == api_key.record.id
    assert key.project_id == api_key.record.project_id
    assert user.id is not None


async def test_auth_context_dataclass_holds_scope() -> None:
    # Arrange / Act
    ctx = AuthContext(user=SimpleNamespace(id="u"), scoped_project_id=None)  # type: ignore[arg-type]

    # Assert
    assert ctx.scoped_project_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd assemblix-app-api && source .venv/bin/activate && pytest tests/integration/test_api_key_scoping.py -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_api.core.auth_context` and `AttributeError: resolve_context`.

- [ ] **Step 3: Create the `AuthContext` type**

Create `assemblix-app-api/assemblix_api/core/auth_context.py`:

```python
"""Authenticated request context shared between the auth dependency and services."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from assemblix_api.database.models.user import User


@dataclass(frozen=True)
class AuthContext:
    """Who is calling and, for API keys, which single project they are scoped to.

    ``scoped_project_id`` is the API key's project for ``sk_`` tokens, or ``None``
    for JWT callers (who may access any project their organization allows).
    """

    user: User
    scoped_project_id: UUID | None
```

- [ ] **Step 4: Add `resolve_context` and refactor `verify_api_key`**

In `assemblix-app-api/assemblix_api/services/api_key_service.py`, replace the body of `verify_api_key` (currently lines ~73-109) and add `resolve_context`. The new methods:

```python
    async def resolve_context(self, plain_key: str) -> tuple[User, APIKey] | None:
        """Resolve a plain key to ``(owner_user, api_key)``.

        Resolves key -> project -> organization -> owner. Increments usage as a
        side effect. Returns ``None`` if the key is invalid/inactive or any link
        in the chain is missing.
        """
        api_key = await self.get_api_key_object(plain_key)
        if not api_key:
            return None

        await self._api_keys.increment_usage(api_key.id)

        project = await self._projects.get_by_id(api_key.project_id)
        if not project:
            return None

        organization = await self._organizations.get_by_id(project.organization_id)
        if not organization:
            return None

        user = await self._users.get_by_id(organization.owner_id)
        if not user:
            return None

        return user, api_key

    async def verify_api_key(self, plain_key: str) -> User | None:
        """Validate an API key and resolve it to the authenticated user."""
        ctx = await self.resolve_context(plain_key)
        return ctx[0] if ctx else None
```

(Leave `get_api_key_object` unchanged — it already performs the `sk_`/length/prefix/hash checks and returns the active `APIKey`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/integration/test_api_key_scoping.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Run the existing api-key/auth tests to confirm no regression**

Run: `pytest tests/integration/test_auth_register.py tests/integration/test_credentials_crud.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add assemblix_api/core/auth_context.py assemblix_api/services/api_key_service.py tests/integration/test_api_key_scoping.py
git commit -m "feat: add AuthContext and APIKeyService.resolve_context"
```

---

### Task 3: `get_auth_context` dependency

**Files:**
- Modify: `assemblix-app-api/assemblix_api/dependencies.py` (add `get_auth_context` near `get_current_user`, ~L746)
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py` (extend)

**Interfaces:**
- Consumes: `AuthContext` (Task 2), `APIKeyService.resolve_context` (Task 2), existing `UserService.get_user_from_token`, existing `_http_bearer`.
- Produces: `async def get_auth_context(...) -> AuthContext` — a FastAPI dependency. For `sk_` tokens returns `AuthContext(user, scoped_project_id=key.project_id)`; for JWT returns `AuthContext(user, scoped_project_id=None)`; raises 401 on invalid key.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_api_key_scoping.py`. This test drives the dependency through a real endpoint that already uses it *after* Task 4, so for now assert the dependency directly:

```python
async def test_get_auth_context_api_key_sets_scope(db_session: Any, api_key) -> None:
    # Arrange
    from fastapi.security import HTTPAuthorizationCredentials

    from assemblix_api.database.repositories.api_key_repository import APIKeyRepository
    from assemblix_api.database.repositories.organization_repository import (
        OrganizationRepository,
    )
    from assemblix_api.database.repositories.project_repository import ProjectRepository
    from assemblix_api.database.repositories.user_repository import UserRepository
    from assemblix_api.dependencies import get_auth_context
    from assemblix_api.services.api_key_service import APIKeyService
    from assemblix_api.services.user_service import UserService

    api_key_service = APIKeyService(
        APIKeyRepository(db_session),
        UserRepository(db_session),
        ProjectRepository(db_session),
        OrganizationRepository(db_session),
    )
    user_service = UserService(
        UserRepository(db_session),
        OrganizationRepository(db_session),
        __import__(
            "assemblix_api.database.repositories.organization_user_repository",
            fromlist=["OrganizationUserRepository"],
        ).OrganizationUserRepository(db_session),
        ProjectRepository(db_session),
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=api_key.plain)

    # Act
    ctx = await get_auth_context(
        credentials=creds, user_service=user_service, api_key_service=api_key_service
    )

    # Assert
    assert ctx.scoped_project_id == api_key.record.project_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_api_key_scoping.py::test_get_auth_context_api_key_sets_scope -v`
Expected: FAIL — `ImportError: cannot import name 'get_auth_context'`.

- [ ] **Step 3: Implement `get_auth_context`**

In `assemblix-app-api/assemblix_api/dependencies.py`, add the import at the top with the other imports:

```python
from assemblix_api.core.auth_context import AuthContext
```

Then add, immediately after `get_current_user` (after ~L771):

```python
async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    user_service: UserService = Depends(get_user_service),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> AuthContext:
    """Resolve the caller and their project scope.

    ``sk_`` tokens are scoped to the key's project; JWT callers are unscoped
    (``scoped_project_id is None``) and fall back to organization-level access checks.
    """
    token = credentials.credentials

    if token.startswith("sk_"):
        ctx = await api_key_service.resolve_context(token)
        if ctx is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный API ключ",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user, api_key = ctx
        structlog.contextvars.bind_contextvars(
            user_id=str(user.id), auth_method="api_key"
        )
        return AuthContext(user=user, scoped_project_id=api_key.project_id)

    user = await user_service.get_user_from_token(token)
    structlog.contextvars.bind_contextvars(user_id=str(user.id), auth_method="jwt")
    return AuthContext(user=user, scoped_project_id=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_api_key_scoping.py::test_get_auth_context_api_key_sets_scope -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/dependencies.py tests/integration/test_api_key_scoping.py
git commit -m "feat: add get_auth_context dependency resolving key project scope"
```

---

### Task 4: `ProjectService.authorize_project_access`

**Files:**
- Modify: `assemblix-app-api/assemblix_api/services/project_service.py` (add method near `verify_user_project_access`, ~L105)
- Test: `assemblix-app-api/tests/unit/services/test_project_authorize.py` (create)

**Interfaces:**
- Consumes: `AuthContext` (Task 2), existing `self.get_by_id`, `self._verify_user_access`.
- Produces: `async def authorize_project_access(self, auth: AuthContext, project_id: UUID) -> Project` — raises 403 if `auth.scoped_project_id` is set and ≠ `project_id`; otherwise delegates to organization-level access check and returns the project.

- [ ] **Step 1: Write the failing test**

Create `assemblix-app-api/tests/unit/services/test_project_authorize.py`:

```python
"""Unit tests for ProjectService.authorize_project_access scope enforcement."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.services.project_service import ProjectService


class _StubRepo:
    def __init__(self, project):
        self._project = project

    async def get_by_id(self, project_id):
        return self._project


def _service(project):
    svc = ProjectService.__new__(ProjectService)
    svc._repository = _StubRepo(project)  # type: ignore[attr-defined]
    return svc


async def test_scoped_key_mismatch_raises_403() -> None:
    # Arrange
    scoped = uuid4()
    other = uuid4()
    project = SimpleNamespace(id=other, organization_id=uuid4())
    svc = _service(project)
    auth = AuthContext(user=SimpleNamespace(id="u"), scoped_project_id=scoped)  # type: ignore[arg-type]

    # Act / Assert
    with pytest.raises(HTTPException) as exc:
        await svc.authorize_project_access(auth, other)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/services/test_project_authorize.py -v`
Expected: FAIL — `AttributeError: authorize_project_access`.

- [ ] **Step 3: Implement the method**

In `assemblix-app-api/assemblix_api/services/project_service.py`, add the import at the top:

```python
from assemblix_api.core.auth_context import AuthContext
```

Then add immediately after `verify_user_project_access` (after ~L109):

```python
    async def authorize_project_access(
        self, auth: AuthContext, project_id: UUID
    ) -> Project:
        """Authorize a request against a project, honoring an API key's scope.

        For API-key callers (``auth.scoped_project_id`` set) any other project is
        rejected outright. JWT callers fall back to organization-level access.
        """
        if auth.scoped_project_id is not None and auth.scoped_project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API-ключ не имеет доступа к этому проекту",
            )
        return await self.verify_user_project_access(auth.user, project_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/services/test_project_authorize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/services/project_service.py tests/unit/services/test_project_authorize.py
git commit -m "feat: add ProjectService.authorize_project_access with key scope check"
```

---

### Task 5: Wire `workflows` router to the scoped check

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/workflows.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py` (extend)

**Interfaces:**
- Consumes: `get_auth_context` (Task 3), `ProjectService.authorize_project_access` (Task 4).
- Produces: workflow CRUD endpoints that reject cross-project API-key access with 403.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_api_key_scoping.py`:

```python
async def _create_workflow(client, headers, project_id, name="WF"):
    return await client.post(
        "/api/workflows/",
        json={"name": name, "projectId": str(project_id)},
        headers=headers,
    )


async def test_list_workflows_rejects_foreign_project(client, api_key, second_project) -> None:
    # Act — key is scoped to auth_user.project; ask for the second project
    resp = await client.get(
        f"/api/workflows/?projectId={second_project}", headers=api_key.headers
    )
    # Assert
    assert resp.status_code == 403


async def test_list_workflows_allows_own_project(client, api_key) -> None:
    # Act
    resp = await client.get(
        f"/api/workflows/?projectId={api_key.record.project_id}", headers=api_key.headers
    )
    # Assert
    assert resp.status_code == 200


async def test_get_foreign_workflow_by_id_forbidden(
    client, api_key, auth_headers, second_project
) -> None:
    # Arrange — a draft workflow in the second project (created via JWT)
    created = await _create_workflow(client, auth_headers, second_project)
    assert created.status_code == 201
    wf_id = created.json()["id"]
    # Act — try to read it with the project-A key
    resp = await client.get(f"/api/workflows/{wf_id}", headers=api_key.headers)
    # Assert
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_api_key_scoping.py -k "workflow" -v`
Expected: FAIL — currently 200 (cross-project access still allowed).

- [ ] **Step 3: Update the router**

In `assemblix-app-api/assemblix_api/api/rest/workflows.py`:

Change the import block:

```python
from assemblix_api.dependencies import (
    get_auth_context,
    get_project_service,
    get_workflow_service,
)
```

and add:

```python
from assemblix_api.core.auth_context import AuthContext
```

(Remove the now-unused `get_current_user` and `User` imports.)

Then in every handler, replace the parameter
`current_user: User = Depends(get_current_user)` with
`auth: AuthContext = Depends(get_auth_context)`, and replace each
`project_service.verify_user_project_access(current_user, <pid>)` with
`project_service.authorize_project_access(auth, <pid>)`. Concretely:

- `list_workflows`: `await project_service.authorize_project_access(auth, project_id)`
- `get_workflow`: `await project_service.authorize_project_access(auth, workflow.project_id)`
- `create_workflow`: `project = await project_service.authorize_project_access(auth, data.project_id)`
- `update_workflow`: `await project_service.authorize_project_access(auth, workflow.project_id)`
- `delete_workflow`: `await project_service.authorize_project_access(auth, workflow.project_id)`
- `publish_workflow`: `await project_service.authorize_project_access(auth, workflow.project_id)`
- `move_workflow`: replace both calls — source `await project_service.authorize_project_access(auth, workflow.project_id)` and target `target_project = await project_service.authorize_project_access(auth, data.target_project_id)`
- `copy_workflow`: `project = await project_service.authorize_project_access(auth, workflow.project_id)`

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_api_key_scoping.py -k "workflow" -v`
Expected: PASS.

- [ ] **Step 5: Run existing workflow tests for regression**

Run: `pytest tests/integration/test_workflow_create.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add assemblix_api/api/rest/workflows.py tests/integration/test_api_key_scoping.py
git commit -m "feat: enforce API key project scope on workflow endpoints"
```

---

### Task 6: Wire `credentials` router to the scoped check

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/credentials.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py` (extend)

**Interfaces:**
- Consumes: `get_auth_context`, `authorize_project_access`.
- Produces: credentials CRUD endpoints that reject cross-project API-key access with 403.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_api_key_scoping.py`:

```python
async def test_list_credentials_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/credentials/?projectId={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403


async def test_create_credentials_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.post(
        "/api/credentials/",
        json={
            "type": "openai_token",
            "value": "sk-x",
            "name": "x",
            "projectId": str(second_project),
        },
        headers=api_key.headers,
    )
    assert resp.status_code == 403


async def test_credentials_own_project_ok(client, api_key) -> None:
    resp = await client.post(
        "/api/credentials/",
        json={
            "type": "openai_token",
            "value": "sk-x",
            "name": "ok",
            "projectId": str(api_key.record.project_id),
        },
        headers=api_key.headers,
    )
    assert resp.status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_api_key_scoping.py -k "credential" -v`
Expected: FAIL for the two `foreign_project` tests (currently 200/201).

- [ ] **Step 3: Update the router**

In `assemblix-app-api/assemblix_api/api/rest/credentials.py`, mirror Task 5:
- imports: add `get_auth_context` (from dependencies) and `from assemblix_api.core.auth_context import AuthContext`; remove `get_current_user` and `User`.
- `list_credentials`, `create_credentials`: `authorize_project_access(auth, project_id)` / `authorize_project_access(auth, data.project_id)`.
- `get_credentials`, `update_credentials`, `delete_credentials`: `authorize_project_access(auth, credentials.project_id)`.
- swap the `current_user: User = Depends(get_current_user)` param for `auth: AuthContext = Depends(get_auth_context)` in all five handlers.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_api_key_scoping.py -k "credential" -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `pytest tests/integration/test_credentials_crud.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add assemblix_api/api/rest/credentials.py tests/integration/test_api_key_scoping.py
git commit -m "feat: enforce API key project scope on credentials endpoints"
```

---

### Task 7: Wire `api_keys` router to the scoped check

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/api_keys.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py` (extend)

**Interfaces:**
- Consumes: `get_auth_context`, `authorize_project_access`.
- Produces: api-key management endpoints that reject cross-project API-key access with 403. (A key can only manage keys within its own project.)

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_api_key_scoping.py`:

```python
async def test_list_api_keys_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/api-keys/?projectId={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_api_key_scoping.py::test_list_api_keys_rejects_foreign_project -v`
Expected: FAIL — currently 200.

- [ ] **Step 3: Update the router**

In `assemblix-app-api/assemblix_api/api/rest/api_keys.py`, mirror the pattern:
- imports: add `get_auth_context` and `from assemblix_api.core.auth_context import AuthContext`; remove `get_current_user` and `User`.
- `list_api_keys`, `create_api_key`: `authorize_project_access(auth, project_id)` / `authorize_project_access(auth, data.project_id)`.
- `get_api_key`, `delete_api_key`: `authorize_project_access(auth, api_key_obj.project_id)` (and `api_key.project_id` respectively).
- swap the `current_user` param for `auth: AuthContext = Depends(get_auth_context)` in all four handlers.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_api_key_scoping.py::test_list_api_keys_rejects_foreign_project -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add assemblix_api/api/rest/api_keys.py tests/integration/test_api_key_scoping.py
git commit -m "feat: enforce API key project scope on api-key endpoints"
```

---

### Task 8: Full gate + docs note

**Files:**
- Modify: `assemblix-app-api/CLAUDE.md` (Auth line, optional clarity) — only if it misstates scoping; otherwise skip.

- [ ] **Step 1: Run the whole backend gate**

Run: `cd assemblix-app-api && source .venv/bin/activate && make check`
Expected: lint/ruff, mypy, bandit, pytest all PASS.

- [ ] **Step 2: Manual sanity (optional, if a dev DB is up)**

Create two projects in one org, make an `sk_` key for project A, and confirm:
`curl -H "Authorization: Bearer sk_..." ".../api/workflows/?projectId=<B>"` → 403;
`...projectId=<A>` → 200.

- [ ] **Step 3: Commit any doc tweak (if made)**

```bash
git add assemblix-app-api/CLAUDE.md
git commit -m "docs: note API keys are hard-scoped to their project"
```

---

## Self-Review

- **Spec coverage:** Part-1 scoping fix → Tasks 2-7. `AuthContext` + `authorize_project_access` → Tasks 2/4. Router swaps (workflows/credentials/api_keys) → Tasks 5/6/7. IDOR-for-execution-keys is closed by the by-id checks in Tasks 5-7 (same helper). Bookkeeping (`.gitignore` + root `CLAUDE.md`) → Task 1. MCP server (Part 2) → separate plan `2026-07-13-assemblix-mcp-server.md`.
- **Placeholder scan:** none — every code step shows full code; the router edits enumerate each handler explicitly.
- **Type consistency:** `AuthContext(user, scoped_project_id)`, `resolve_context -> tuple[User, APIKey] | None`, `authorize_project_access(auth, project_id) -> Project` used identically across tasks.
- **Known limitation (from spec):** actions via a key remain attributed to the org owner; not addressed here.
- **Note:** published workflows stay publicly readable (existing behavior); the scope check applies only to the access-protected branches. `move_workflow` to another project via a scoped key returns 403 by design.
