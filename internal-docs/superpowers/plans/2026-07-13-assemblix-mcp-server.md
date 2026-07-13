# Assemblix MCP Server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standalone Python/FastMCP server (`assemblix-mcp`) that exposes workflow and credentials CRUD as MCP tools, authenticated with a single project-scoped `sk_` key, runnable both as a hosted HTTP service and locally via `uvx`.

**Architecture:** Thin client over the Assemblix REST API. One `AssemblixClient` (httpx) wraps the endpoints and injects the `sk_` bearer. Tools never take `project_id` — the key defines the project (enforced server-side by the scoping fix in the core repo). Key resolution has two modes: from env (`ASSEMBLIX_API_KEY`, stdio/local) or from the incoming HTTP `Authorization` header (hosted, per-user).

**Tech Stack:** Python 3.11+, FastMCP v3 (`/prefecthq/fastmcp`), httpx, pydantic, pytest + respx (HTTP mocking), `uv` for packaging.

## Prerequisite

The core scoping fix (`internal-docs/superpowers/plans/2026-07-13-project-api-key-scoping.md`) must be **deployed** to the target Assemblix instance. Without it, tools still work but keys are not project-isolated.

## Global Constraints

- **This lives in `assemblix-aitools/` — a SEPARATE git repo** (gitignored by the core repo). Init git there; do NOT commit these files into the core repo.
- License: **MIT** (distinct from the core's MIT + Commons Clause).
- All comments/docstrings in English; minimal, only for non-trivial logic.
- Package name / distribution: PyPI `assemblix-mcp`, console entry `assemblix-mcp`, `uvx assemblix-mcp` must work.
- `project_id` is NEVER a tool parameter or client argument — it is implicit in the key.
- Config via env only: `ASSEMBLIX_API_URL` (default `https://app.assmblx.com`), `ASSEMBLIX_API_KEY` (required for stdio; optional for HTTP where the header supplies it).
- FastMCP API (verified via context7): `from fastmcp import FastMCP`; `@mcp.tool` decorator; `mcp.run()` = stdio; `mcp.run(transport="http", host=..., port=...)` = streamable HTTP; per-request headers via `from fastmcp.server.dependencies import get_http_headers`.

## File Structure

```
assemblix-aitools/                     # separate repo root
  mcp/                                 # the assemblix-mcp package project
    pyproject.toml                     # package metadata + entry point + deps
    README.md                          # install (hosted + uvx), config, tool list
    LICENSE                            # MIT
    src/assemblix_mcp/
      __init__.py
      config.py                        # env + per-request key resolution
      client.py                        # AssemblixClient (httpx wrapper)
      server.py                        # FastMCP instance + transport selection (main)
      tools/
        __init__.py
        workflows.py                   # workflow tools
        credentials.py                 # credentials tools
    tests/
      test_client.py
      test_workflow_tools.py
      test_credentials_tools.py
```

---

### Task 1: Bootstrap the separate repo + package skeleton

**Files:**
- Create: `assemblix-aitools/mcp/pyproject.toml`
- Create: `assemblix-aitools/mcp/LICENSE`
- Create: `assemblix-aitools/mcp/src/assemblix_mcp/__init__.py`
- Create: `assemblix-aitools/mcp/README.md`

**Interfaces:**
- Produces: an installable package `assemblix-mcp` with console script `assemblix-mcp -> assemblix_mcp.server:main` and dependencies `fastmcp>=3`, `httpx`, `pydantic>=2`.

- [ ] **Step 1: Initialize the independent git repo**

Run:
```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git init
mkdir -p mcp/src/assemblix_mcp/tools mcp/tests
```

- [ ] **Step 2: Write `pyproject.toml`**

Create `assemblix-aitools/mcp/pyproject.toml`:

```toml
[project]
name = "assemblix-mcp"
version = "0.1.0"
description = "MCP server for Assemblix — workflows & credentials over a project API key"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "fastmcp>=3",
    "httpx>=0.27",
    "pydantic>=2",
]

[project.scripts]
assemblix-mcp = "assemblix_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/assemblix_mcp"]

[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "respx>=0.21"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Write `LICENSE` and `__init__.py`**

Create `assemblix-aitools/mcp/LICENSE` with the standard MIT license text (copyright holder: the Assemblix authors, year 2026).

Create `assemblix-aitools/mcp/src/assemblix_mcp/__init__.py`:

```python
"""Assemblix MCP server package."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write a minimal `README.md`**

Create `assemblix-aitools/mcp/README.md` with a title, one-line description, and two install snippets (fill the tool list in Task 6):

````markdown
# assemblix-mcp

MCP server for [Assemblix](https://app.assmblx.com). Drive your project's workflows
and credentials from any MCP client using a single project API key (`sk_...`).

## Install

### Hosted (easiest — nothing to install)

```
claude mcp add --transport http assemblix https://mcp.assmblx.com \
  --header "Authorization: Bearer sk_your_key"
```

### Local (uvx)

```
claude mcp add assemblix -- \
  env ASSEMBLIX_API_KEY=sk_your_key ASSEMBLIX_API_URL=https://app.assmblx.com \
  uvx assemblix-mcp
```

## Configuration

| Env var | Default | Notes |
| --- | --- | --- |
| `ASSEMBLIX_API_URL` | `https://app.assmblx.com` | Base URL of your Assemblix instance |
| `ASSEMBLIX_API_KEY` | — | Project `sk_` key. Required for stdio; for hosted HTTP the `Authorization` header is used instead |
| `ASSEMBLIX_MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `ASSEMBLIX_MCP_HOST` / `ASSEMBLIX_MCP_PORT` | `0.0.0.0` / `8000` | HTTP transport bind |
````

- [ ] **Step 5: Sync and confirm the environment builds**

Run:
```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools/mcp
uv sync
```
Expected: resolves `fastmcp`, `httpx`, `pydantic`, and dev deps with no error.

- [ ] **Step 6: Commit (in the assemblix-aitools repo)**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git add mcp/
git commit -m "chore: scaffold assemblix-mcp package"
```

---

### Task 2: `config.py` — env + per-request key resolution

**Files:**
- Create: `assemblix-aitools/mcp/src/assemblix_mcp/config.py`
- Test: `assemblix-aitools/mcp/tests/test_client.py` (start the file here)

**Interfaces:**
- Produces:
  - `Settings` (pydantic) with `api_url: str`, `api_key: str | None`, `transport: str`, `host: str`, `port: int`, loaded from env via `Settings.from_env()`.
  - `resolve_api_key(settings: Settings, header_value: str | None) -> str` — returns the bearer token: prefers an incoming `Authorization: Bearer <k>` header value, else `settings.api_key`; raises `ValueError` if neither is present.

- [ ] **Step 1: Write the failing test**

Create `assemblix-aitools/mcp/tests/test_client.py`:

```python
import pytest

from assemblix_mcp.config import Settings, resolve_api_key


def test_resolve_prefers_header():
    s = Settings(api_url="http://x", api_key="sk_env", transport="http", host="h", port=1)
    assert resolve_api_key(s, "Bearer sk_header") == "sk_header"


def test_resolve_falls_back_to_env():
    s = Settings(api_url="http://x", api_key="sk_env", transport="stdio", host="h", port=1)
    assert resolve_api_key(s, None) == "sk_env"


def test_resolve_raises_without_any_key():
    s = Settings(api_url="http://x", api_key=None, transport="stdio", host="h", port=1)
    with pytest.raises(ValueError):
        resolve_api_key(s, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd assemblix-aitools/mcp && uv run pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_mcp.config`.

- [ ] **Step 3: Implement `config.py`**

Create `assemblix-aitools/mcp/src/assemblix_mcp/config.py`:

```python
"""Configuration and per-request API key resolution."""

from __future__ import annotations

import os

from pydantic import BaseModel


class Settings(BaseModel):
    api_url: str
    api_key: str | None
    transport: str
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_url=os.environ.get("ASSEMBLIX_API_URL", "https://app.assmblx.com"),
            api_key=os.environ.get("ASSEMBLIX_API_KEY"),
            transport=os.environ.get("ASSEMBLIX_MCP_TRANSPORT", "stdio"),
            host=os.environ.get("ASSEMBLIX_MCP_HOST", "0.0.0.0"),
            port=int(os.environ.get("ASSEMBLIX_MCP_PORT", "8000")),
        )


def resolve_api_key(settings: Settings, header_value: str | None) -> str:
    """Return the bearer token, preferring an incoming Authorization header."""
    if header_value:
        token = header_value.removeprefix("Bearer ").strip()
        if token:
            return token
    if settings.api_key:
        return settings.api_key
    raise ValueError(
        "No API key: set ASSEMBLIX_API_KEY or send an Authorization: Bearer header."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git add mcp/src/assemblix_mcp/config.py mcp/tests/test_client.py
git commit -m "feat: settings + api key resolution"
```

---

### Task 3: `client.py` — httpx wrapper over the REST API

**Files:**
- Create: `assemblix-aitools/mcp/src/assemblix_mcp/client.py`
- Test: `assemblix-aitools/mcp/tests/test_client.py` (extend)

**Interfaces:**
- Consumes: `Settings` (Task 2).
- Produces: `AssemblixClient(base_url: str, api_key: str)` with async methods returning parsed JSON (`dict`/`list`):
  - workflows: `list_workflows(**filters)`, `get_workflow(workflow_id)`, `create_workflow(name, **fields)`, `update_workflow(workflow_id, **fields)`, `delete_workflow(workflow_id)`, `get_project_id()`.
  - credentials: `list_credentials(**filters)`, `get_credentials(credentials_id)`, `create_credentials(type, value, name)`, `update_credentials(credentials_id, **fields)`, `delete_credentials(credentials_id)`.
  - Raises `AssemblixAPIError(status_code, detail)` on non-2xx.
  - `project_id` is resolved by the client from the key via `GET /api/api-keys/` is NOT needed — instead the client discovers it lazily; see note in Step 3.

- [ ] **Step 1: Write the failing test**

Append to `assemblix-aitools/mcp/tests/test_client.py`:

```python
import httpx
import respx

from assemblix_mcp.client import AssemblixAPIError, AssemblixClient


@respx.mock
async def test_list_workflows_sends_bearer_and_project(monkeypatch):
    # Arrange
    client = AssemblixClient(base_url="http://api.test", api_key="sk_k", project_id="p1")
    route = respx.get("http://api.test/api/workflows/").mock(
        return_value=httpx.Response(200, json=[{"id": "w1"}])
    )
    # Act
    result = await client.list_workflows()
    # Assert
    assert result == [{"id": "w1"}]
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer sk_k"
    assert sent.url.params["projectId"] == "p1"


@respx.mock
async def test_error_response_raises():
    client = AssemblixClient(base_url="http://api.test", api_key="sk_k", project_id="p1")
    respx.get("http://api.test/api/workflows/w9").mock(
        return_value=httpx.Response(403, json={"detail": "nope"})
    )
    try:
        await client.get_workflow("w9")
        assert False, "expected error"
    except AssemblixAPIError as e:
        assert e.status_code == 403
        assert "nope" in e.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py -k "workflows_sends or error_response" -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_mcp.client`.

- [ ] **Step 3: Implement `client.py`**

Create `assemblix-aitools/mcp/src/assemblix_mcp/client.py`:

```python
"""Thin async HTTP client over the Assemblix REST API."""

from __future__ import annotations

from typing import Any

import httpx


class AssemblixAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


class AssemblixClient:
    """One instance per request; carries the caller's key and project scope.

    ``project_id`` is the scope of the API key. For CRUD endpoints that take a
    ``projectId`` query/body param it is injected automatically so tools never
    accept it. Endpoints addressed by resource id do not need it.
    """

    def __init__(self, base_url: str, api_key: str, project_id: str) -> None:
        self._base = base_url.rstrip("/")
        self._project_id = project_id
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def _request(
        self, method: str, path: str, *, params: dict | None = None, json: dict | None = None
    ) -> Any:
        async with httpx.AsyncClient(base_url=self._base, headers=self._headers) as http:
            resp = await http.request(method, path, params=params, json=json)
        if resp.status_code >= 400:
            detail = _extract_detail(resp)
            raise AssemblixAPIError(resp.status_code, detail)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # --- workflows ---
    async def list_workflows(self, **filters: Any) -> Any:
        params = {"projectId": self._project_id, **_clean(filters)}
        return await self._request("GET", "/api/workflows/", params=params)

    async def get_workflow(self, workflow_id: str) -> Any:
        return await self._request("GET", f"/api/workflows/{workflow_id}")

    async def create_workflow(self, name: str, **fields: Any) -> Any:
        body = {"name": name, "projectId": self._project_id, **_clean(fields)}
        return await self._request("POST", "/api/workflows/", json=body)

    async def update_workflow(self, workflow_id: str, **fields: Any) -> Any:
        return await self._request(
            "PATCH", f"/api/workflows/{workflow_id}", json=_clean(fields)
        )

    async def delete_workflow(self, workflow_id: str) -> Any:
        return await self._request("DELETE", f"/api/workflows/{workflow_id}")

    # --- credentials ---
    async def list_credentials(self, **filters: Any) -> Any:
        params = {"projectId": self._project_id, **_clean(filters)}
        return await self._request("GET", "/api/credentials/", params=params)

    async def get_credentials(self, credentials_id: str) -> Any:
        return await self._request("GET", f"/api/credentials/{credentials_id}")

    async def create_credentials(self, type: str, value: str, name: str) -> Any:
        body = {"type": type, "value": value, "name": name, "projectId": self._project_id}
        return await self._request("POST", "/api/credentials/", json=body)

    async def update_credentials(self, credentials_id: str, **fields: Any) -> Any:
        return await self._request(
            "PATCH", f"/api/credentials/{credentials_id}", json=_clean(fields)
        )

    async def delete_credentials(self, credentials_id: str) -> Any:
        return await self._request("DELETE", f"/api/credentials/{credentials_id}")


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _extract_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except Exception:
        pass
    return resp.text or resp.reason_phrase
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git add mcp/src/assemblix_mcp/client.py mcp/tests/test_client.py
git commit -m "feat: AssemblixClient REST wrapper with auto project scope"
```

---

### Task 4: Resolving the key's `project_id`

**Files:**
- Modify: `assemblix-aitools/mcp/src/assemblix_mcp/client.py` (add a project-id discovery helper)
- Test: `assemblix-aitools/mcp/tests/test_client.py` (extend)

**Interfaces:**
- Produces: `async def fetch_project_id(base_url: str, api_key: str) -> str` — a module-level helper that resolves the key's project without the caller supplying it. It calls `GET /api/api-keys/?projectId=` is not possible (needs project). Instead it uses a scope-echo: `GET /api/workflows/` with a sentinel projectId returns 403 revealing nothing — so we add a dedicated tiny endpoint. **Decision:** add `GET /api/api-keys/whoami` to the core API returning `{ "projectId": ... }` for the calling key. See Step 3 for the fallback if that endpoint is unavailable.

- [ ] **Step 1: Add `GET /api/api-keys/whoami` to the core API (prerequisite in the other repo)**

In the **core repo**, add to `assemblix_api/api/rest/api_keys.py`:

```python
from assemblix_api.dependencies import get_project_id_from_token


@router.get("/whoami")
async def whoami(project_id: UUID = Depends(get_project_id_from_token)) -> dict[str, str]:
    """Return the project the calling API key is scoped to."""
    return {"projectId": str(project_id)}
```

Commit that in the core repo (its own PR): `feat: api-keys whoami returns the key's project`. `get_project_id_from_token` already resolves the key → project.

- [ ] **Step 2: Write the failing test**

Append to `assemblix-aitools/mcp/tests/test_client.py`:

```python
@respx.mock
async def test_fetch_project_id():
    from assemblix_mcp.client import fetch_project_id

    respx.get("http://api.test/api/api-keys/whoami").mock(
        return_value=httpx.Response(200, json={"projectId": "p-42"})
    )
    pid = await fetch_project_id("http://api.test", "sk_k")
    assert pid == "p-42"
```

- [ ] **Step 3: Implement `fetch_project_id`**

Append to `assemblix-aitools/mcp/src/assemblix_mcp/client.py`:

```python
async def fetch_project_id(base_url: str, api_key: str) -> str:
    """Resolve the key's project via the whoami endpoint."""
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {api_key}"},
    ) as http:
        resp = await http.get("/api/api-keys/whoami")
    if resp.status_code >= 400:
        raise AssemblixAPIError(resp.status_code, _extract_detail(resp))
    return str(resp.json()["projectId"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py::test_fetch_project_id -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git add mcp/src/assemblix_mcp/client.py mcp/tests/test_client.py
git commit -m "feat: resolve key project via whoami"
```

---

### Task 5: Workflow tools

**Files:**
- Create: `assemblix-aitools/mcp/src/assemblix_mcp/tools/__init__.py`
- Create: `assemblix-aitools/mcp/src/assemblix_mcp/tools/workflows.py`
- Test: `assemblix-aitools/mcp/tests/test_workflow_tools.py`

**Interfaces:**
- Consumes: `AssemblixClient` (Task 3). A `client_for_request()` provider (defined in `server.py`, Task 7) that builds a per-request `AssemblixClient`. To keep tools testable in isolation, tools take the client via a small indirection: `register_workflow_tools(mcp, get_client)` where `get_client: Callable[[], Awaitable[AssemblixClient]]`.
- Produces: `register_workflow_tools(mcp, get_client)` registering: `list_workflows`, `get_workflow`, `create_workflow`, `update_workflow`, `delete_workflow`.

- [ ] **Step 1: Write the failing test**

Create `assemblix-aitools/mcp/tests/test_workflow_tools.py`:

```python
import httpx
import respx
from fastmcp import FastMCP
from fastmcp import Client as MCPClient

from assemblix_mcp.client import AssemblixClient
from assemblix_mcp.tools.workflows import register_workflow_tools


def _build_server():
    mcp = FastMCP("test")

    async def get_client():
        return AssemblixClient(base_url="http://api.test", api_key="sk_k", project_id="p1")

    register_workflow_tools(mcp, get_client)
    return mcp


@respx.mock
async def test_list_workflows_tool_returns_data():
    respx.get("http://api.test/api/workflows/").mock(
        return_value=httpx.Response(200, json=[{"id": "w1", "name": "A"}])
    )
    mcp = _build_server()
    async with MCPClient(mcp) as c:
        result = await c.call_tool("list_workflows", {})
    assert result.data == [{"id": "w1", "name": "A"}]


@respx.mock
async def test_create_workflow_tool_posts_name():
    route = respx.post("http://api.test/api/workflows/").mock(
        return_value=httpx.Response(201, json={"id": "w2", "name": "New"})
    )
    mcp = _build_server()
    async with MCPClient(mcp) as c:
        result = await c.call_tool("create_workflow", {"name": "New"})
    assert result.data["id"] == "w2"
    body = route.calls.last.request.content
    assert b'"name": "New"' in body or b'"name":"New"' in body
    assert b"projectId" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workflow_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_mcp.tools.workflows`.

- [ ] **Step 3: Implement the tools**

Create `assemblix-aitools/mcp/src/assemblix_mcp/tools/__init__.py`:

```python
"""MCP tool registration."""
```

Create `assemblix-aitools/mcp/src/assemblix_mcp/tools/workflows.py`:

```python
"""Workflow MCP tools. project_id is implicit in the API key."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastmcp import FastMCP

from assemblix_mcp.client import AssemblixClient

GetClient = Callable[[], Awaitable[AssemblixClient]]


def register_workflow_tools(mcp: FastMCP, get_client: GetClient) -> None:
    @mcp.tool
    async def list_workflows(
        is_active: bool | None = None,
        is_published: bool | None = None,
        is_template: bool | None = None,
    ) -> Any:
        """List the project's workflows (optionally filtered by status)."""
        client = await get_client()
        return await client.list_workflows(
            isActive=is_active, isPublished=is_published, isTemplate=is_template
        )

    @mcp.tool
    async def get_workflow(workflow_id: str) -> Any:
        """Get a workflow by id, including nodes, edges and state."""
        client = await get_client()
        return await client.get_workflow(workflow_id)

    @mcp.tool
    async def create_workflow(name: str, description: str | None = None) -> Any:
        """Create a new draft workflow in the project."""
        client = await get_client()
        return await client.create_workflow(name=name, description=description)

    @mcp.tool
    async def update_workflow(
        workflow_id: str,
        name: str | None = None,
        description: str | None = None,
        nodes: list | None = None,
        edges: list | None = None,
    ) -> Any:
        """Update a workflow. All fields optional."""
        client = await get_client()
        return await client.update_workflow(
            workflow_id, name=name, description=description, nodes=nodes, edges=edges
        )

    @mcp.tool
    async def delete_workflow(workflow_id: str) -> Any:
        """Permanently delete a workflow."""
        client = await get_client()
        await client.delete_workflow(workflow_id)
        return {"deleted": workflow_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workflow_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git add mcp/src/assemblix_mcp/tools/ mcp/tests/test_workflow_tools.py
git commit -m "feat: workflow MCP tools"
```

---

### Task 6: Credentials tools

**Files:**
- Create: `assemblix-aitools/mcp/src/assemblix_mcp/tools/credentials.py`
- Test: `assemblix-aitools/mcp/tests/test_credentials_tools.py`
- Modify: `assemblix-aitools/mcp/README.md` (fill the tool list)

**Interfaces:**
- Consumes: `AssemblixClient`, the same `get_client` indirection.
- Produces: `register_credentials_tools(mcp, get_client)` registering: `list_credentials`, `get_credentials`, `create_credentials`, `update_credentials`, `delete_credentials`.

- [ ] **Step 1: Write the failing test**

Create `assemblix-aitools/mcp/tests/test_credentials_tools.py`:

```python
import httpx
import respx
from fastmcp import Client as MCPClient
from fastmcp import FastMCP

from assemblix_mcp.client import AssemblixClient
from assemblix_mcp.tools.credentials import register_credentials_tools


def _server():
    mcp = FastMCP("test")

    async def get_client():
        return AssemblixClient(base_url="http://api.test", api_key="sk_k", project_id="p1")

    register_credentials_tools(mcp, get_client)
    return mcp


@respx.mock
async def test_create_credentials_tool():
    route = respx.post("http://api.test/api/credentials/").mock(
        return_value=httpx.Response(201, json={"id": "c1", "type": "openai_token"})
    )
    async with MCPClient(_server()) as c:
        result = await c.call_tool(
            "create_credentials",
            {"type": "openai_token", "value": "sk-x", "name": "My key"},
        )
    assert result.data["id"] == "c1"
    assert b"projectId" in route.calls.last.request.content


@respx.mock
async def test_list_credentials_tool():
    respx.get("http://api.test/api/credentials/").mock(
        return_value=httpx.Response(200, json=[{"id": "c1"}])
    )
    async with MCPClient(_server()) as c:
        result = await c.call_tool("list_credentials", {})
    assert result.data == [{"id": "c1"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_credentials_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_mcp.tools.credentials`.

- [ ] **Step 3: Implement the tools**

Create `assemblix-aitools/mcp/src/assemblix_mcp/tools/credentials.py`:

```python
"""Credentials MCP tools. Secret values are write-only; never returned."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastmcp import FastMCP

from assemblix_mcp.client import AssemblixClient

GetClient = Callable[[], Awaitable[AssemblixClient]]


def register_credentials_tools(mcp: FastMCP, get_client: GetClient) -> None:
    @mcp.tool
    async def list_credentials(type: str | None = None) -> Any:
        """List the project's credentials (secret values are never returned)."""
        client = await get_client()
        return await client.list_credentials(type=type)

    @mcp.tool
    async def get_credentials(credentials_id: str) -> Any:
        """Get credential metadata by id (secret value is never returned)."""
        client = await get_client()
        return await client.get_credentials(credentials_id)

    @mcp.tool
    async def create_credentials(type: str, value: str, name: str) -> Any:
        """Create a provider credential. ``type`` e.g. openai_token/gemini_token."""
        client = await get_client()
        return await client.create_credentials(type=type, value=value, name=name)

    @mcp.tool
    async def update_credentials(
        credentials_id: str, name: str | None = None, value: str | None = None
    ) -> Any:
        """Update a credential's name and/or secret value. Type cannot change."""
        client = await get_client()
        return await client.update_credentials(credentials_id, name=name, value=value)

    @mcp.tool
    async def delete_credentials(credentials_id: str) -> Any:
        """Permanently delete a credential."""
        client = await get_client()
        await client.delete_credentials(credentials_id)
        return {"deleted": credentials_id}
```

- [ ] **Step 4: Fill the README tool list**

In `assemblix-aitools/mcp/README.md`, add:

```markdown
## Tools

**Workflows:** `list_workflows`, `get_workflow`, `create_workflow`, `update_workflow`, `delete_workflow`
**Credentials:** `list_credentials`, `get_credentials`, `create_credentials`, `update_credentials`, `delete_credentials`

All tools operate on the single project your API key is scoped to. `projectId` is never a parameter.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_credentials_tools.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git add mcp/src/assemblix_mcp/tools/credentials.py mcp/tests/test_credentials_tools.py mcp/README.md
git commit -m "feat: credentials MCP tools + README tool list"
```

---

### Task 7: `server.py` — assemble, dual transport, per-request client

**Files:**
- Create: `assemblix-aitools/mcp/src/assemblix_mcp/server.py`
- Test: `assemblix-aitools/mcp/tests/test_workflow_tools.py` (add a wiring smoke test)

**Interfaces:**
- Consumes: `Settings.from_env` (Task 2), `resolve_api_key` (Task 2), `AssemblixClient` + `fetch_project_id` (Tasks 3-4), `register_workflow_tools`, `register_credentials_tools`.
- Produces:
  - `build_server(settings: Settings) -> FastMCP` — registers tools with a `get_client` that resolves the key (env or per-request header via `get_http_headers`), fetches the project id, and returns an `AssemblixClient`.
  - `main() -> None` — entry point; builds from env and calls `mcp.run()` (stdio) or `mcp.run(transport="http", host, port)` per `settings.transport`.

- [ ] **Step 1: Write the failing smoke test**

Append to `assemblix-aitools/mcp/tests/test_workflow_tools.py`:

```python
def test_build_server_registers_all_tools():
    import asyncio

    from assemblix_mcp.config import Settings
    from assemblix_mcp.server import build_server

    settings = Settings(
        api_url="http://api.test", api_key="sk_k", transport="stdio", host="h", port=1
    )
    mcp = build_server(settings)
    names = {t.name for t in asyncio.run(mcp.get_tools()).values()}
    assert {"list_workflows", "create_workflow", "list_credentials"} <= names
```

(If `mcp.get_tools()` returns a coroutine of a dict keyed by name in the installed FastMCP version, the assertion above works; if it returns a list, adjust to `{t.name for t in ...}`. Verify the exact shape against the installed version with `uv run python -c "import asyncio; from fastmcp import FastMCP; m=FastMCP('x'); print(asyncio.run(m.get_tools()))"` before implementing.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workflow_tools.py::test_build_server_registers_all_tools -v`
Expected: FAIL — `ModuleNotFoundError: assemblix_mcp.server`.

- [ ] **Step 3: Implement `server.py`**

Create `assemblix-aitools/mcp/src/assemblix_mcp/server.py`:

```python
"""FastMCP server assembly and entry point."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from assemblix_mcp.client import AssemblixClient, fetch_project_id
from assemblix_mcp.config import Settings, resolve_api_key
from assemblix_mcp.tools.credentials import register_credentials_tools
from assemblix_mcp.tools.workflows import register_workflow_tools


def build_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("assemblix")

    async def get_client() -> AssemblixClient:
        headers = get_http_headers() or {}
        api_key = resolve_api_key(settings, headers.get("authorization"))
        project_id = await fetch_project_id(settings.api_url, api_key)
        return AssemblixClient(
            base_url=settings.api_url, api_key=api_key, project_id=project_id
        )

    register_workflow_tools(mcp, get_client)
    register_credentials_tools(mcp, get_client)
    return mcp


def main() -> None:
    settings = Settings.from_env()
    mcp = build_server(settings)
    if settings.transport == "http":
        mcp.run(transport="http", host=settings.host, port=settings.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workflow_tools.py::test_build_server_registers_all_tools -v`
Expected: PASS. (If FastMCP's `get_http_headers()` errors outside an HTTP request during `build_server`, note it is only called inside `get_client` at tool-call time, so `build_server` stays safe.)

- [ ] **Step 5: Manual smoke — stdio boots**

Run: `ASSEMBLIX_API_KEY=sk_dummy uv run assemblix-mcp` then send Ctrl-C.
Expected: process starts a stdio MCP server without import errors (it will wait for stdin — Ctrl-C to exit).

- [ ] **Step 6: Commit**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git add mcp/src/assemblix_mcp/server.py mcp/tests/test_workflow_tools.py
git commit -m "feat: server assembly with dual transport + per-request client"
```

---

### Task 8: Full test run + end-to-end check against a live API

**Files:** none (verification only).

- [ ] **Step 1: Run the whole suite**

Run: `cd assemblix-aitools/mcp && uv run pytest -v`
Expected: all PASS.

- [ ] **Step 2: End-to-end against a running Assemblix (with the scoping fix deployed)**

Start the core stack, create a project `sk_` key, then:

```bash
ASSEMBLIX_API_KEY=sk_realkey ASSEMBLIX_API_URL=http://localhost:8000 \
  uv run assemblix-mcp
```

Connect an MCP client (e.g. `fastmcp` `Client`, or `claude mcp add`) and call `list_workflows` — expect the project's workflows. Then confirm scope isolation is server-side: the tool has no `projectId` param, so cross-project access is structurally impossible from the client.

- [ ] **Step 3: (optional) HTTP transport check**

Run: `ASSEMBLIX_MCP_TRANSPORT=http ASSEMBLIX_MCP_PORT=8765 uv run assemblix-mcp`, then
`claude mcp add --transport http assemblix-local http://localhost:8765 --header "Authorization: Bearer sk_realkey"` and call a tool.

- [ ] **Step 4: Tag a pre-release (optional)**

```bash
cd /Users/nmamizerov/Desktop/alfa/assemblix/assemblix-aitools
git tag mcp-v0.1.0
```

---

## Self-Review

- **Spec coverage:** Standalone Python/FastMCP server → Tasks 1,7. Thin REST client, project implicit from key → Tasks 3,4. Workflow CRUD tools → Task 5. Credentials CRUD tools → Task 6. Both transports (hosted HTTP + local stdio/uvx) → Tasks 1 (packaging), 2 (config), 7 (transport switch). Per-user key via header in hosted mode → Tasks 2,7. Separate repo + MIT + gitignore boundary → Task 1 + core Plan Task 1. Distribution snippets → README (Tasks 1,6).
- **Placeholder scan:** none — every code step is complete. Task 7 Step 1 flags a version-shape verification for `get_tools()` with an exact command to run first (not a placeholder — a guarded assertion).
- **Type consistency:** `AssemblixClient(base_url, api_key, project_id)`, `fetch_project_id(base_url, api_key) -> str`, `register_workflow_tools(mcp, get_client)`, `register_credentials_tools(mcp, get_client)`, `build_server(settings) -> FastMCP`, `resolve_api_key(settings, header_value) -> str` used identically across tasks.
- **Cross-repo dependency:** Task 4 Step 1 adds `GET /api/api-keys/whoami` to the **core** repo (small, its own commit/PR). The scoping Plan is the other prerequisite. Both must be deployed before Task 8 Step 2.
- **Deliberately out of scope:** execution/run tools, knowledge-base tools, skills, and Claude Code plugins (future work in the same `assemblix-aitools` repo).
