# Project API keys + standalone MCP server — design

**Date:** 2026-07-13
**Status:** Approved design (pre-implementation)

## Goal

Make the workflow and credentials CRUD endpoints (create / update / list / detail)
safely usable with a **project-scoped API key**, so an external **MCP server** for
Assemblix can drive them with a single `sk_` key. The MCP server is shipped and used
**separately** from the core product.

## Background — current state (as found in code)

- **API-key auth already exists and already works on these endpoints.**
  `get_current_user` ([dependencies.py](../../../assemblix-app-api/assemblix_api/dependencies.py)
  around L746) accepts both a JWT and an `sk_` token. `sk_` is verified via
  `APIKeyService.verify_api_key`.
- All four routers (`workflows`, `credentials`, `api_keys`) follow the same shape:
  `get_current_user` → `project_service.verify_user_project_access(current_user, project_id)`.
- **Scoping gap (the real problem):** `verify_api_key` resolves
  `key → project → organization → owner_id` and returns the **org owner** as the
  authenticated user. The CRUD endpoints take `project_id` **from the request**
  (query/body, or derived from the fetched resource) and then
  `verify_user_project_access` grants access to **any project in the org**.
  → A "project A" key can currently read/write workflows and credentials of
  projects B, C, … in the same organization. For a "separately shippable" MCP key
  this is effectively an org-wide key, not a project key.
- Execution endpoints already scope correctly via `get_project_id_from_token`
  (project_id taken **from the key**). The CRUD endpoints do not.

## Decisions

1. **MCP architecture:** standalone Python service, thin client over the REST API,
   authenticated with one `sk_` key. Not embedded in FastAPI.
2. **Scoping:** hard scope from the key. When authenticated via an API key, the
   effective project is the key's project; a request referencing any other project
   → `403`. JWT/front-end behaviour is unchanged.
3. **Runtime:** Python + FastMCP. Both transports from one codebase: hosted HTTP
   (remote MCP) **and** local stdio via `uvx`.
4. **Repo layout:** development happens inside this folder, but under a new
   subfolder `assemblix-aitools/` which is a **separate, independent git repo**.
   It is added to this repo's `.gitignore` and documented in the root `CLAUDE.md`.
   It houses the MCP server plus future skills and Claude Code plugins.

## Part 1 — Scoping fix (core repo `assemblix-app-api`)

Chosen approach: a single auth-context dependency + one authorize helper (uniform,
minimal surface, also fixes the existing IDOR for execution keys).

1. **`AuthContext`** returned by a new `get_auth_context` dependency (wraps the
   existing `get_current_user` logic):
   ```python
   @dataclass
   class AuthContext:
       user: User
       scoped_project_id: UUID | None   # key's project for sk_; None for JWT
   ```

2. **`ProjectService.authorize_project_access(auth: AuthContext, project_id) -> Project`**
   — does what `verify_user_project_access` does, **plus**: if
   `auth.scoped_project_id is not None and auth.scoped_project_id != project_id`
   → raise `403`.

3. Replace `verify_user_project_access(current_user, project_id)` with
   `authorize_project_access(auth, project_id)` in the `workflows`, `credentials`,
   and `api_keys` routers.
   - `list` / `create` (project_id from query/body): the check rejects a foreign
     project.
   - `get` / `update` / `delete` by id (project_id derived from the fetched
     resource): the check rejects touching a resource that belongs to another
     project. **This also closes the same IDOR for existing execution keys.**

**Not changed / known limitation:** actions performed via an API key remain
attributed to the org owner (current `verify_api_key` model). Out of scope for this
iteration; noted explicitly.

## Pre-plan check

Before writing the implementation plan, verify the **current** FastMCP usage via
context7 (`resolve-library-id` → `query-docs`): server setup, tool definitions, and
how both transports (hosted HTTP + local stdio/`uvx`) are wired in the current
version. Do not rely on memory — the API may have changed.

## Part 2 — Standalone MCP server (`assemblix-aitools/`)

- New independent repo at `assemblix-aitools/` (own toolchain). First artifact:
  the MCP server, published to PyPI as `assemblix-mcp`.
- Python + FastMCP. Config via env: `ASSEMBLIX_API_URL`, `ASSEMBLIX_API_KEY` (`sk_`).
- Tools map 1:1 to the endpoints; **`project_id` is NOT a tool argument** — it is
  implicit from the key:
  - `list_workflows`, `get_workflow`, `create_workflow`, `update_workflow`,
    `delete_workflow`
  - `list_credentials`, `get_credentials`, `create_credentials`,
    `update_credentials`, `delete_credentials`
- Execution tools are out of scope for this iteration (noted as next step).

### Distribution (both, from one codebase)

- **Hosted remote MCP (easiest):** you deploy one instance (e.g. `mcp.assmblx.com`);
  users add URL + their key:
  ```
  claude mcp add --transport http assemblix https://mcp.assmblx.com \
    --header "Authorization: Bearer sk_..."
  ```
  Claude Desktop / Cursor: "Add custom connector → URL + header".
- **Local via uvx (self-host / privacy):**
  ```
  claude mcp add assemblix -- \
    env ASSEMBLIX_API_KEY=sk_... ASSEMBLIX_API_URL=https://app.assmblx.com uvx assemblix-mcp
  ```

## Repo / bookkeeping changes (core repo)

- Add `/assemblix-aitools/` to the root `.gitignore`.
- Document in the root `CLAUDE.md`: `assemblix-aitools/` is a separate, independent
  repo (MCP server + future skills + Claude Code plugins), gitignored here, its own
  toolchain and license (MIT); the scoping fix lives in core.

## Testing

- **Backend (integration):**
  - Project-A key against project-B `project_id` (query/body) → 403.
  - Project-A key against a project-B resource by id → 403.
  - Same-project key → success.
  - JWT path unchanged (no regression).
  - Execution key IDOR closed.
- **MCP:** tool tests against a mocked REST layer; assert `project_id` is never
  accepted from the caller.

## Affected files (core repo)

- `assemblix_api/dependencies.py` — `AuthContext` + `get_auth_context`
- `assemblix_api/services/project_service.py` — `authorize_project_access`
- `assemblix_api/api/rest/workflows.py`, `credentials.py`, `api_keys.py` — swap call
- root `.gitignore`, root `CLAUDE.md` — bookkeeping
- new independent repo: `assemblix-aitools/`
