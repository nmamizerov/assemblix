# Test Writing Rules (Assemblix API)

This document is the single source of truth for **how** to write tests in
`assemblix-app-api`. Read it before adding any test.

---

## 0. Mandatory process rules (from the user)

> **When developing new functionality, it is mandatory to first ask the user for
> the test cases that need to be covered and describe them.**

That is, you must not "invent" tests on the user's behalf. The order is:

1. A task for a new feature / behavior change comes in.
2. **Ask the user for the list of test cases** (what exactly to check: inputs,
   expected results, edge cases, errors).
3. Describe the agreed cases (e.g. as a list in the PR/issue/docstrings).
4. Only after that, write the tests themselves and the implementation.

The scaffolding (fixtures, DB container, mocks) is shared and reused; the specific
cases always come from the user's requirements.

> **Never change the logic of existing tests without prior agreement.**

If a test fails, the default assumption is that the **implementation** is wrong, not
the test. You must not "fix" a test by altering what it asserts, loosening
expectations, deleting cases, or changing its inputs/expected results just to make it
pass. The order is:

1. A test fails or seems wrong.
2. **Stop and ask the user** before touching the test's logic — explain why you
   think the test (and not the code under test) needs to change.
3. Only after the user agrees, modify the test.

Mechanical, behavior-preserving edits (renaming, formatting, fixing imports, moving a
test, updating a fixture name after a rename) do not require agreement. Anything that
changes **what** a test verifies does.

---

## 1. Test architecture

Three layers, each with its own directory under `tests/`:

| Layer | Directory | DB | Redis | LLM | When |
|-------|-----------|----|-------|-----|------|
| **unit** | `tests/unit/` | container is up, but the test does not hit the DB | `fake_redis` | `mock_llm` | logic of a single unit on mocks |
| **integration** | `tests/integration/` | real Postgres in a container | `fake_redis` | `mock_llm` | layer integration, API endpoints, DB |
| **external** | `tests/external/` | container is up | `fake_redis` | **real requests, real keys** | verifying real providers |

Facts to remember:

- The Postgres container is started **once per session** (via testcontainers) and
  destroyed at the end. The DB is fresh on each run.
- After **each test** the transaction is rolled back → data does not leak between
  tests. Nothing needs to be cleaned up manually.
- Redis everywhere is `fakeredis` (in-memory), not a container (Redis is optional in
  the product).
- LLM providers are mocked at a single point — `litellm.acompletion`.
- Run pytest **only from the `assemblix-app-api/` directory** (that's where
  `pyproject.toml` with `asyncio_mode=auto` lives). From the repo root the config is
  not picked up.

---

## 2. AAA (Arrange–Act–Assert) pattern — mandatory

Each test is split into three explicit sections with comments:

- **Arrange** — prepare data/environment (payload, fixtures, mock setup).
- **Act** — the single action under test (one call).
- **Assert** — checks on the result.

Example (`tests/integration/test_auth_register.py`):

```python
async def test_register_returns_token(client) -> None:
    """POST /api/auth/register with a simple email/password/name → 201 + token."""
    # Arrange
    payload = {
        "email": "alice@example.com",
        "password": "pass1234",
        "fullName": "Alice",
    }

    # Act
    resp = await client.post("/api/auth/register", json=payload)

    # Assert
    assert resp.status_code == 201
    body = resp.json()
    assert body["accessToken"]
    assert body["tokenType"] == "bearer"
```

AAA rules:

- Exactly **one** meaningful call in Act.
- Arrange must contain no assertions; Assert must contain no new actions (other than
  reading the result, e.g. `resp.json()`).
- If there are several tests for one endpoint — a separate function per case, do not
  multiply Act within a single test.

---

## 3. Available fixtures

Shared fixtures are split into focused modules under `tests/plugins/` (database,
app, auth, llm) and registered globally via `pytest_plugins` in `tests/conftest.py`
— which itself keeps only the container bootstrap hooks. Scope-local fixtures live
in nested conftests (e.g. `tests/integration/queue/conftest.py`). Available globally:

| Fixture | What it provides |
|---------|------------------|
| `db_session` | Transactional async SQLAlchemy session (rolled back after the test) |
| `app` | FastAPI app with `get_db_session` overridden by the test session |
| `client` | `httpx.AsyncClient` over ASGI (no network) |
| `user_factory` | User factory: `await user_factory()` → namespace (user, token, organization_id, project_id) |
| `auth_user` | A ready-made user (creates org + default project + JWT) |
| `auth_headers` | `{"Authorization": "Bearer <jwt>"}` for `auth_user` |
| `api_key` | `sk_` key for the user's project: `api_key.plain`, `api_key.headers` |
| `mock_llm` | Patches `litellm.acompletion`; `mock_llm.set_response(...)`, `queue_responses(...)` |
| `fake_redis` | In-memory Redis |

Data builders (plain functions, not fixtures) — in `tests/fixtures/`:

- `tests/fixtures/workflows.py` — graphs (`linear_agent_workflow`, `condition_branch_workflow`, `node`, `edge`).
- `tests/fixtures/llm_responses.py` — LLM response templates (`text_response`, `json_response`, `tool_call_response`).

---

## 4. Mocking LLM providers

All providers (OpenAI/Gemini/DeepSeek) go through a single
`litellm.acompletion` call. We test **our** system, not the provider.

```python
async def test_agent_uses_mocked_llm(mock_llm, ...) -> None:
    # Arrange
    mock_llm.set_response("expected answer", prompt_tokens=12, completion_tokens=8)

    # Act
    ...  # a run that triggers the agent node

    # Assert
    assert mock_llm.call_count == 1
    assert mock_llm.calls[0]["model"] == "openai/gpt-4o"
```

For multi-step scenarios (tool-loop / several turns):
`mock_llm.queue_responses("first", "second")`.

---

## 5. Real providers (external)

- Directory `tests/external/`, each file/test is marked `pytestmark = pytest.mark.external`.
- Keys come from env (`SYSTEM_OPENAI_API_KEY`, etc.); if a key is missing — `pytest.skip(...)`,
  the test does **not** fail.
- They are **not** part of the base scope or CI (`-m "not external"`). Run manually:
  `make test-external`.

---

## 6. Conventions

- **Comments and docstrings — English only** (project rule).
- A test docstring briefly describes the case (what → what).
- On the wire DTOs are **camelCase** (`fullName`, `accessToken`, `projectId`), inside
  Python — snake_case (conversion is automatic via `DTOModel`).
- File names: `test_<area>.py`; functions: `test_<behavior>`.
- HTTP endpoints with permissions — pass `auth_headers` (JWT) or `api_key.headers`;
  for project scope use `auth_user.project_id`.
- Do not assert "guessed" behavior — check against the real code/response (for
  example, when creating a workflow without a graph, the service seeds a default
  START graph, not an empty list).

---

## 7. Running

```bash
# from the assemblix-app-api/ directory
make test            # base set: unit + integration (needs Docker)
make test-cov        # same + coverage (fail_under threshold)
make test-external   # only real providers (needs real keys)

# targeted
uv run pytest tests/integration/test_auth_register.py
uv run pytest tests/integration/test_auth_register.py::test_register_returns_token -v
```

---

## 8. Reuse setup — fixtures over copy-paste (mandatory)

When the same **Arrange** setup repeats across 2+ tests (registering a user,
creating an API key, creating an entity to read/update/delete, etc.), extract it —
do not copy-paste:

- **Fixture** = pytest's `@BeforeEach`. Put per-test setup in a
  `@pytest_asyncio.fixture` that returns what the tests need (an id, a namespace,
  headers). Request it by adding its name as a test argument. This is the default
  choice for shared setup.
- **Helper function** for a small reusable step a fixture (or several tests) calls
  internally, e.g. `_create_kb(client, headers, project_id)`.

Rules:

- Keep the **action under test in the test itself** — never hide the `Act` call in a
  fixture. A `test_create_*` does its own `POST`; only `test_get/update/delete`
  consume a fixture that created the entity.
- Fixtures returning a namespace (`types.SimpleNamespace`) are fine for bundling
  several values (headers + ids).
- Scope: default to function scope (`@BeforeEach`). The DB is rolled back / truncated
  per test, so module/session-scoped data setup usually does NOT survive — only use
  wider scopes for loop/engine-style resources, not for rows.

Examples in the suite:

- `routing_setup` in `tests/integration/test_workflow_routing_session.py` — registers
  a user, mints a key, creates the workflow, arms `mock_llm`.
- `knowledge_base` in `tests/integration/test_knowledge_base_crud.py` — creates a KB
  and returns its id for the read/update/delete tests.
