# API Key Scoping — Remaining Routers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Extend the project-API-key hard-scope (already applied to workflows/credentials/api_keys) to EVERY other router that accepts `sk_` keys, so a project-A key cannot touch another project's data anywhere. Close the residual surface found by the final review of `feat/project-api-key-scoping`.

**Architecture:** Same mechanism as the prior branch: `auth: AuthContext = Depends(get_auth_context)` + `ProjectService.authorize_project_access(auth, project_id)` (raises 403 when the key's `scoped_project_id` is set and != `project_id`; JWT → `scoped_project_id=None` → unchanged org-level check). Two flavors:
- **Router-level:** the handler already calls `verify_user_project_access(current_user, X)` — swap the param and the call. Mechanical, proven in Tasks 5-7.
- **Service-level:** authorization lives inside a service method that only takes `current_user` and derives the project from a fetched resource. Add an optional `scoped_project_id: UUID | None = None` parameter and enforce it against the resolved project inside the service; the router passes `auth.scoped_project_id`.

**Tech Stack:** Python 3.13, FastAPI, async SQLAlchemy, pytest (integration via httpx client + real Postgres).

## Global Constraints

- All comments/docstrings in English; minimal, only for non-trivial logic.
- No business logic in routers; no SQLAlchemy in services; no HTTPException in repositories.
- TDD: failing test first (cross-project currently returns 2xx), then implement, then pass.
- **Query-param footgun (from Tasks 5-7):** list endpoints take a bare `project_id: UUID = Query(...)` — snake_case, NOT DTO-aliased. Integration tests hitting a list endpoint must use `?project_id=<id>`, never `?projectId=`. JSON request bodies DO use camelCase (`"projectId"`).
- Tests live in `assemblix-app-api/tests/integration/test_api_key_scoping.py` (extend it). Reuse the existing `api_key`, `auth_headers`, `second_project`, `client` fixtures already in that file.
- The swap must convert EVERY listed handler in a file — a single missed handler is a security hole.
- Preserve all existing behavior other than adding the scope check.
- `source .venv/bin/activate`; run from `assemblix-app-api/`. If integration tests error on DB: `cd .. && docker compose -f docker-compose.dev.yml up -d postgres`, retry.
- Do NOT hand-edit versions/CHANGELOG; if `uv run` bumps `uv.lock` version, `git checkout uv.lock` before committing.
- Never touch the execute/run endpoints already scoped via `get_project_id_from_token*` (`execute_workflow`, `execute_workflow_debug`, `execute_workflow_audio`, `execute_workflow_debug_audio`, `get_task_execution_result`, `in_flight_executions`).
- End commit message body with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## The mechanical swap (applies to every router-level handler below)

For each handler:
1. Replace the parameter `current_user: User = Depends(get_current_user)` with `auth: AuthContext = Depends(get_auth_context)`.
2. Replace `project_service.verify_user_project_access(current_user, <pid>)` with `project_service.authorize_project_access(auth, <pid>)` (keep `<pid>` exactly as it was — query param, `data.project_id`, or `<resource>.project_id`).
3. If the handler passes `current_user` to a service for anything else, use `auth.user`.
4. Update imports: add `get_auth_context` (from `assemblix_api.dependencies`) and `from assemblix_api.core.auth_context import AuthContext`; remove `get_current_user` and the `User` import if now unused.

---

### Task 1: Session routers (client_sessions.py + chat_sessions.py)

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/client_sessions.py`
- Modify: `assemblix-app-api/assemblix_api/api/rest/chat_sessions.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py`

**Interfaces:**
- Consumes: `get_auth_context`, `authorize_project_access` (from the prior branch).
- Produces: both routers reject cross-project API-key access with 403.

Handlers to convert (all router-level, `verify_user_project_access(current_user, project_id)`):
- `client_sessions.py`: `list_client_sessions`, `get_client_session`, `list_client_session_executions`, `list_client_chat_sessions`, `update_client_session_metadata`, `deactivate_client_session` (6).
- `chat_sessions.py`: `list_chat_sessions`, `get_chat_session_detail`, `rename_chat_session`, `delete_chat_session`, `send_message_to_session` (5).

- [ ] **Step 1: Write failing tests** — append to `test_api_key_scoping.py`:

```python
async def test_list_client_sessions_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/client-sessions/?project_id={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403


async def test_list_chat_sessions_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/chat-sessions/?project_id={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403
```

Note: verify the exact list route prefixes from each router's `APIRouter(prefix=...)` (e.g. `/client-sessions`, `/chat-sessions`) and the exact query-param name on the list handler; adjust the URLs if they differ. The assertion is 403 either way.

- [ ] **Step 2: Run** `pytest tests/integration/test_api_key_scoping.py -k "client_sessions or chat_sessions" -v` → FAIL (currently 200).
- [ ] **Step 3: Apply the mechanical swap** to all 11 handlers across both files.
- [ ] **Step 4: Run** the same `-k` selection → PASS.
- [ ] **Step 5: Commit** `feat: enforce API key project scope on session routers`.

---

### Task 2: Content routers (knowledge_bases.py + node_templates.py + notification_channels.py)

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/knowledge_bases.py`
- Modify: `assemblix-app-api/assemblix_api/api/rest/node_templates.py`
- Modify: `assemblix-app-api/assemblix_api/api/rest/notification_channels.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py`

**Interfaces:**
- Consumes: `get_auth_context`, `authorize_project_access`.
- Produces: all three routers reject cross-project API-key access with 403 (list/create via request project_id; get/update/delete via the fetched resource's `project_id`).

Handlers to convert (all router-level):
- `knowledge_bases.py` (11): `list_knowledge_bases`, `get_knowledge_base`, `create_knowledge_base`, `update_knowledge_base`, `delete_knowledge_base`, `list_documents`, `get_document`, `upload_text_document`, `upload_pdf_document`, `delete_document`. (Every `verify_user_project_access` call in the file — list uses `project_id`, create uses `data.project_id`, the rest use `kb.project_id`.)
- `node_templates.py` (5): `list_node_templates`, `get_node_template`, `create_node_template`, `update_node_template`, `delete_node_template`.
- `notification_channels.py` (6): `list_notification_channels`, `get_notification_channel`, `create_notification_channel`, `update_notification_channel`, `delete_notification_channel`, `test_notification_channel`.

- [ ] **Step 1: Write failing tests** — append to `test_api_key_scoping.py` (confirm each router's list prefix + query-param name first):

```python
async def test_list_knowledge_bases_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/knowledge-bases/?project_id={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403


async def test_list_node_templates_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/node-templates/?project_id={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403


async def test_list_notification_channels_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/notification-channels/?project_id={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run** `pytest tests/integration/test_api_key_scoping.py -k "knowledge or node_templates or notification" -v` → FAIL.
- [ ] **Step 3: Apply the mechanical swap** to all 22 handlers.
- [ ] **Step 4: Run** the same `-k` selection → PASS.
- [ ] **Step 5: Commit** `feat: enforce API key project scope on knowledge base / node template / notification routers`.

---

### Task 3: executions.py (router-level list + service-level detail/stream)

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/executions.py`
- Modify: `assemblix-app-api/assemblix_api/services/execution_service.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py`

**Interfaces:**
- Consumes: `get_auth_context`, `authorize_project_access`, `AuthContext`.
- Produces:
  - `list_executions` rejects a foreign `project_id` with 403 (router-level swap).
  - `ExecutionService.get_execution_detail(execution_id, current_user, scoped_project_id: UUID | None = None)` — after it resolves the execution's project, if `scoped_project_id is not None and scoped_project_id != execution.project_id` raise `HTTPException(403)`. `get_execution_detail` and `stream_execution_events` routers pass `scoped_project_id=auth.scoped_project_id`.

- [ ] **Step 1: Inspect** `ExecutionService.get_execution_detail` to find where it resolves the execution and its `project_id` (it already fetches the execution and checks org membership). Note the variable holding the execution's `project_id`.

- [ ] **Step 2: Write failing tests** — append to `test_api_key_scoping.py`:

```python
async def test_list_executions_rejects_foreign_project(client, api_key, second_project) -> None:
    resp = await client.get(
        f"/api/executions/?project_id={second_project}", headers=api_key.headers
    )
    assert resp.status_code == 403
```

(Confirm the list-executions route path + query-param name from the router before finalizing the URL. A detail/stream cross-project test needs a foreign execution to exist, which is heavy to set up; the router change is covered by the service-level guard — assert the guard with a focused unit-style test on `get_execution_detail` only if the service shape makes it cheap; otherwise rely on the list test plus the guard code and note it.)

- [ ] **Step 3: Run** `pytest tests/integration/test_api_key_scoping.py -k executions -v` → FAIL.

- [ ] **Step 4: Implement**
  - Router `list_executions`: apply the mechanical swap.
  - Service `get_execution_detail`: add `scoped_project_id: UUID | None = None` param; after the execution's project is known, insert:
    ```python
    if scoped_project_id is not None and scoped_project_id != execution.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API-ключ не имеет доступа к этому проекту")
    ```
    (Use the actual variable name for the execution and its project id found in Step 1. `HTTPException`/`status` are already imported in services elsewhere — mirror the existing import style in this service file; if not present, import from `fastapi`.)
  - Routers `get_execution_detail` and `stream_execution_events`: swap `current_user` → `auth: AuthContext = Depends(get_auth_context)`, pass `current_user=auth.user, scoped_project_id=auth.scoped_project_id` to the service call.

- [ ] **Step 5: Run** `pytest tests/integration/test_api_key_scoping.py -k executions -v` → PASS. Also run `pytest tests/integration/ -k execution -v` to check no execution regression.
- [ ] **Step 6: Commit** `feat: enforce API key project scope on execution list and detail`.

---

### Task 4: projects.py

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/projects.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py`

**Interfaces:**
- Consumes: `get_auth_context`, `authorize_project_access`.
- Produces: `get_project`, `update_project`, `delete_project` reject a foreign `project_id` (path param) with 403 for a scoped key. `list_projects` and `create_project` stay org-level (no single project_id) and are documented as such.

Handlers:
- `get_project` (router-level: `service.verify_user_project_access(current_user, project_id)`) → `service.authorize_project_access(auth, project_id)`.
- `update_project` (same) → swap.
- `delete_project` (service-level: `service.delete_project(project_id, current_user)`): add a scope check in the router BEFORE the delete, since `project_id` is a path param:
  ```python
  await service.authorize_project_access(auth, project_id)
  await service.delete_project(project_id, auth.user)
  ```
- `list_projects`, `create_project`: leave unchanged (org-scoped by design — a key can enumerate/create projects in its own org). Add a one-line English comment on each noting this is intentional org-level access.

- [ ] **Step 1: Write failing tests** — append to `test_api_key_scoping.py`:

```python
async def test_get_foreign_project_forbidden(client, api_key, second_project) -> None:
    resp = await client.get(f"/api/projects/{second_project}", headers=api_key.headers)
    assert resp.status_code == 403


async def test_delete_foreign_project_forbidden(client, api_key, second_project) -> None:
    resp = await client.delete(f"/api/projects/{second_project}", headers=api_key.headers)
    assert resp.status_code == 403


async def test_get_own_project_ok(client, api_key) -> None:
    resp = await client.get(f"/api/projects/{api_key.record.project_id}", headers=api_key.headers)
    assert resp.status_code == 200
```

- [ ] **Step 2: Run** `pytest tests/integration/test_api_key_scoping.py -k project -v` → the foreign-project tests FAIL (currently 200/204).
- [ ] **Step 3: Implement** the swaps + the `delete_project` router-level guard + import updates.
- [ ] **Step 4: Run** `pytest tests/integration/test_api_key_scoping.py -k project -v` → PASS.
- [ ] **Step 5: Commit** `feat: enforce API key project scope on project detail/update/delete`.

---

### Task 5: avatar.py + voice.py (router-level credential lists + service-level mint)

**Files:**
- Modify: `assemblix-app-api/assemblix_api/api/rest/avatar.py`
- Modify: `assemblix-app-api/assemblix_api/api/rest/voice.py`
- Modify: `assemblix-app-api/assemblix_api/services/avatar_service.py`
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py`

**Interfaces:**
- Consumes: `get_auth_context`, `authorize_project_access`, `AuthContext`.
- Produces:
  - `avatar.list_credential_avatars`, `avatar.list_credential_voices`, `voice.list_credential_voices` reject a foreign credential (whose project != key scope) with 403 (router-level: they already call `verify_user_project_access(current_user, credentials.project_id)` → swap).
  - `avatar.list_providers` / `avatar.list_provider_models` / `voice.list_providers` / `voice.list_provider_models` / `voice.list_system_voices`: auth-only, no project — swap the param to `auth` for import consistency ONLY if they reference `current_user`; if they only need authentication, leave `get_current_user` (do NOT introduce an unused scope). Prefer minimal change: keep these on `get_current_user`.
  - `AvatarService.mint_workflow_session(workflow_id, current_user, scoped_project_id: UUID | None = None)` — after resolving the workflow's project, if `scoped_project_id is not None and scoped_project_id != workflow.project_id` raise `HTTPException(403)`. The `mint_avatar_session` router passes `scoped_project_id=auth.scoped_project_id`.

- [ ] **Step 1: Inspect** `AvatarService.mint_workflow_session` to find where the workflow (and its `project_id`) is resolved.

- [ ] **Step 2: Write failing test** — append to `test_api_key_scoping.py`. Create a credential in `second_project` via JWT, then list its avatars with the project-A key:

```python
async def test_list_credential_avatars_foreign_credential_forbidden(
    client, api_key, auth_headers, second_project
) -> None:
    created = await client.post(
        "/api/credentials/",
        json={"type": "anam_token", "value": "an-x", "name": "foreign", "projectId": str(second_project)},
        headers=auth_headers,
    )
    assert created.status_code == 201
    cred_id = created.json()["id"]
    resp = await client.get(f"/api/avatar/credentials/{cred_id}/avatars", headers=api_key.headers)
    assert resp.status_code == 403
```

Confirm the exact avatar route path (`/api/avatar/credentials/{id}/avatars` or similar) from the router before finalizing. Verify `anam_token` is a valid `CredentialsType`; if not, use a credential type that IS valid for the avatar-list endpoint.

- [ ] **Step 3: Run** `pytest tests/integration/test_api_key_scoping.py -k "credential_avatars" -v` → FAIL (currently reaches provider call / non-403).
- [ ] **Step 4: Implement**
  - `avatar.py` / `voice.py`: swap the three `list_credential_*` handlers (param + `authorize_project_access(auth, credentials.project_id)` + imports). Leave provider/system-voice list handlers on `get_current_user`.
  - `AvatarService.mint_workflow_session`: add `scoped_project_id` param + the 403 guard after the workflow is resolved.
  - `mint_avatar_session` router: swap to `auth`, pass `scoped_project_id=auth.scoped_project_id` and `auth.user`.
- [ ] **Step 5: Run** `pytest tests/integration/test_api_key_scoping.py -k "credential_avatars" -v` → PASS.
- [ ] **Step 6: Commit** `feat: enforce API key project scope on avatar and voice credential endpoints`.

---

### Task 6: JWT positive regression test + full gate

**Files:**
- Test: `assemblix-app-api/tests/integration/test_api_key_scoping.py`

**Interfaces:**
- Produces: closes the one untested branch of `authorize_project_access` (a JWT caller with `scoped_project_id=None` still reaches a second same-org project) + a green whole-suite gate.

- [ ] **Step 1: Write the test** — append to `test_api_key_scoping.py`:

```python
async def test_jwt_can_access_second_project_in_org(client, auth_headers, second_project) -> None:
    # A JWT caller (scoped_project_id=None) is NOT restricted to a single project.
    resp = await client.get(
        f"/api/workflows/?project_id={second_project}", headers=auth_headers
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run** `pytest tests/integration/test_api_key_scoping.py -v` → all PASS (including the new JWT case).
- [ ] **Step 3: Full gate** — `make check` → ruff/format/mypy/bandit + full pytest green. If ruff format flags the new/edited files, run `uv run ruff format <files>` and re-run. `git checkout uv.lock` if it got a version bump.
- [ ] **Step 4: Commit** `test: JWT caller can access any same-org project (scope=None regression)`.

---

## Self-Review

- **Spec coverage:** Every router the final review enumerated is covered — session routers (Task 1), knowledge/node/notification (Task 2), executions list+detail/stream (Task 3), projects (Task 4), avatar+voice (Task 5). The Minor JWT test gap → Task 6.
- **Placeholder scan:** Tasks 1/2/4 fully specify handlers + the proven mechanical swap + concrete tests. Tasks 3/5 specify the exact service-method signature change and the 403 guard snippet, with a Step-1 inspection to bind the real variable names (the one unavoidable lookup, called out explicitly — not a placeholder).
- **Type consistency:** `authorize_project_access(auth, project_id) -> Project`, `AuthContext(user, scoped_project_id)`, and the added `scoped_project_id: UUID | None = None` service params are used identically across tasks.
- **Intentional non-changes:** execute/run endpoints (already scoped via `get_project_id_from_token*`); `projects.list_projects`/`create_project` (org-level by design, documented); avatar/voice provider-list & system-voice handlers (auth-only, no project) stay on `get_current_user`.
