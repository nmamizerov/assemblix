# Node SDK Contributor Guide

This guide explains how to add new node types to Assemblix — either **in-tree** (as
part of the core codebase) or **out-of-tree** (as an installable plugin package). Every
node works the same way at runtime: the registry dispatches execution to a `BaseNode`
subclass, and the frontend renders its form automatically from the descriptor you declare.

---

## Table of Contents

1. [Core concepts](#core-concepts)
2. [In-tree node: step-by-step](#in-tree-node-step-by-step)
3. [Worked example: DelayNode](#worked-example-delaynode)
4. [Out-of-tree plugin](#out-of-tree-plugin)
5. [Property-type reference](#property-type-reference)
6. [Conditional fields and repeatable sub-objects](#conditional-fields-and-repeatable-sub-objects)
7. [Capability hooks](#capability-hooks)
8. [Frontend rendering](#frontend-rendering)

---

## Core concepts

The execution engine resolves a node type string (e.g. `"delay"`) to a `BaseNode`
subclass via the **`NodeRegistry`** singleton. The registry is string-keyed — there is
no enum to edit and no database migration required when adding a new node type. The
`node_type` column in PostgreSQL is `VARCHAR`; unknown type strings round-trip safely
through the `GenericNode` schema fallback.

Built-in nodes are loaded by importing `assemblix_api.nodes` at startup. Plugin nodes
are loaded via Python entry points in the `assemblix.nodes` group.

---

## In-tree node: step-by-step

### 1. Subclass `BaseNode`

```python
# assemblix-app-api/assemblix_api/nodes/my_node.py

from assemblix_api.core.node_registry import register_node
from assemblix_api.schemas.execution import NodeInput, NodeOutput
from assemblix_api.schemas.node import BaseNode
from assemblix_api.schemas.node_descriptor import NodeDescriptor, NodeProperty


@register_node("my_type")
class MyNode(BaseNode):
    async def execute(self, node_input: NodeInput) -> NodeOutput:
        # node_input.data   — dict passed from the previous node's output
        # node_input.context — ExecutionContext (read-only immutable dataclass)
        result = {"answer": 42}
        return NodeOutput(data=result)

    @classmethod
    def descriptor(cls) -> NodeDescriptor | None:
        return NodeDescriptor(
            type="my_type",
            display_name="My Node",
            description="Does something useful.",
            category="logic",
            icon="Zap",          # any Lucide icon name
            color="node-logic",
            properties=[
                NodeProperty(
                    name="my_param",
                    display_name="My Param",
                    type="string",
                    required=True,
                    description="A required text input.",
                ),
            ],
        )
```

Key points:
- `@register_node("my_type")` accepts a plain string or a `NodeType` enum member.
  For new nodes, use a plain string — do not add to the `NodeType` enum unless the
  node needs to be part of the built-in discriminated union.
- `execute` is `async`. Return `NodeOutput(data=...)` at minimum.
- `descriptor()` — the base-class signature is `-> NodeDescriptor | None`. Returning
  `None` hides the node from the catalog (used by START, PLACEHOLDER, and other internal
  node types). A plugin node should always return a concrete `NodeDescriptor`. The
  example above annotates the override as `-> NodeDescriptor | None` to match the parent
  and satisfy mypy; returning a concrete descriptor is the normal plugin case.

### 2. Add the import to `nodes/__init__.py`

```python
# assemblix-app-api/assemblix_api/nodes/__init__.py
from .my_node import MyNode  # noqa: F401
```

Add `"MyNode"` to `__all__` as well. The `@register_node` decorator fires on import,
so the node is available the moment the backend starts.

### 3. No migration, no enum edit needed

The `node_type` column is `VARCHAR`. Workflow definitions containing `"my_type"` nodes
are stored and retrieved without any schema change. At execution time the registry
resolves `"my_type"` → `MyNode`. If the node type is unknown (e.g. the plugin is
uninstalled), the graph validator will surface a clear error rather than crashing
silently — the `GenericNode` fallback keeps the definition parseable but the executor
will raise `NodeTypeNotRegisteredError`.

---

## Worked example: DelayNode

The `DelayNode` is the canonical in-tree example. Its full source lives at
`assemblix-app-api/assemblix_api/nodes/delay_node.py` and is reproduced here for
reference:

```python
"""DELAY node — pauses the workflow for a bounded number of seconds, then passes
input through unchanged. Serves as the reference SDK example (see CONTRIBUTING_NODES.md)."""

import asyncio

from assemblix_api.core.node_registry import register_node
from assemblix_api.schemas.execution import NodeInput, NodeOutput
from assemblix_api.schemas.node import BaseNode
from assemblix_api.schemas.node_descriptor import NodeDescriptor, NodeProperty

_MAX_DELAY_SECONDS = 300.0


@register_node("delay")
class DelayNode(BaseNode):
    async def execute(self, node_input: NodeInput) -> NodeOutput:
        seconds = float(self.node_config.get("config", {}).get("seconds", 0) or 0)
        seconds = max(0.0, min(seconds, _MAX_DELAY_SECONDS))
        await asyncio.sleep(seconds)
        return NodeOutput(data=node_input.data)

    @classmethod
    def descriptor(cls) -> NodeDescriptor | None:
        return NodeDescriptor(
            type="delay", display_name="Delay",
            description="Pauses the workflow for a fixed number of seconds.",
            category="logic", icon="Clock", color="node-logic",
            properties=[
                NodeProperty(
                    name="seconds", display_name="Seconds", type="number",
                    default=1, required=True,
                    description=f"0–{int(_MAX_DELAY_SECONDS)} seconds.",
                ),
            ],
        )
```

Notice:
- Config is read from `self.node_config["config"]` — that dict is what the frontend
  sends when saving the workflow.
- The node passes `node_input.data` straight through (`pass-through pattern`).
- The descriptor declares a single `number` property; the frontend renders a numeric
  input automatically — no React code required.

---

## Out-of-tree plugin

You can ship a node as a separate pip package without touching the core codebase.

### Package layout

```
my-assemblix-nodes/
  pyproject.toml
  my_nodes/
    __init__.py       # empty or re-exports
    nodes.py          # @register_node decorated classes
```

### `pyproject.toml` entry-point declaration

```toml
[project]
name = "my-assemblix-nodes"
version = "0.1.0"
dependencies = ["assemblix-app-api>=0.1"]   # or pin a compatible range

[project.entry-points."assemblix.nodes"]
my_nodes = "my_nodes.nodes"
```

The entry-point value (`"my_nodes.nodes"`) is the importable module path.
`ep.load()` imports that module, firing every `@register_node` decorator inside
it automatically. An optional `:attribute` target (e.g. `"my_nodes.nodes:register"`)
also works if you prefer an explicit callable, but is not required.

The entry-point **name** (`my_nodes`) is used only for logging and can be any string.
You can register multiple entry points in one package.

### Install and discover

```bash
pip install ./my-assemblix-nodes   # or from PyPI: pip install my-assemblix-nodes
```

On the next backend startup, `load_plugin_nodes()` (called automatically during
application startup) discovers and loads every entry point in the `assemblix.nodes`
group. Zero changes to the core repository are needed. A broken plugin is logged and
skipped — startup always completes.

### Plugin execution and persistence

When a workflow containing a plugin node type runs:
- The node type string (e.g. `"my_nodes"`) is stored as-is in the execution step log.
- The registry resolves it to your `BaseNode` subclass at execution time.
- The `GenericNode` schema accepts the raw config dict without validation, so the
  workflow definition is parseable even when the plugin is not installed. When it is
  installed, your own Pydantic models (used inside `execute`) validate the config.

---

## Property-type reference

The `PropertyType` literal determines how the frontend generic renderer draws the form
field. No React code is needed for these types — the renderer reads `descriptor().properties`
and constructs the form automatically.

| `type`           | When to use                                                        | Frontend widget                        |
|------------------|--------------------------------------------------------------------|----------------------------------------|
| `"string"`       | Short single-line text (URL, name, key)                           | Text input                             |
| `"text"`         | Multi-line free text (system prompt, template body)               | Textarea                               |
| `"number"`       | Numeric value (timeout, count, threshold)                         | Numeric input                          |
| `"boolean"`      | On/off toggle                                                     | Checkbox / toggle switch               |
| `"options"`      | Fixed set of choices (provide `options: [NodePropertyOption]`)    | Select / dropdown                      |
| `"json"`         | Arbitrary JSON object or array                                    | JSON editor                            |
| `"code"`         | Code snippet (e.g. CEL expression, script)                        | Code editor (monospace)                |
| `"credential"`   | Reference to a stored credential                                  | Credential picker                      |
| `"knowledge_base"` | Reference to a knowledge base                                   | Knowledge base picker                  |
| `"key_value"`    | Flat map of string → string pairs (headers, query params)         | Key-value pair editor                  |
| `"collection"`   | List of repeatable structured sub-objects (use `fields`)          | Repeatable form section                |

### `NodeProperty` fields

> **camelCase config keys** — `GenericNodeForm` converts `NodeProperty.name` from
> snake_case to camelCase before writing to the stored `config` dict
> (`snakeToCamel(property.name)`). A property declared as `name="max_retries"` is
> stored and must be read as `config["maxRetries"]`, not `config["max_retries"]`.
> **Tip:** prefer single-word names (e.g. `seconds`, `timeout`) to avoid any
> ambiguity; if you must use multi-word names, read the camelCase form in `execute()`.

```python
class NodeProperty:
    name: str                         # stored as camelCase in the config dict (snakeToCamel applied by the frontend)
    display_name: str                 # human-readable label shown in the UI
    type: PropertyType
    default: Any = None               # pre-filled value
    required: bool = False
    placeholder: str | None = None
    description: str | None = None    # helper text shown below the field
    options: list[NodePropertyOption] = []   # for type="options" only
    show_when: NodeDisplayCondition | None = None   # conditional visibility
    fields: list[NodeProperty] = []  # for type="collection" only
```

### `NodePropertyOption`

```python
class NodePropertyOption:
    value: str   # stored in config
    label: str   # shown to the user
```

---

## Conditional fields and repeatable sub-objects

### `showWhen` — conditional visibility

Use `show_when` to hide a property unless a sibling field holds a specific value:

```python
NodeProperty(
    name="source_node_id",
    display_name="Source Node",
    type="string",
    show_when=NodeDisplayCondition(field="output_mode", values=["specific_agent"]),
),
```

`NodeDisplayCondition.field` is the `name` of the controlling property.
`NodeDisplayCondition.values` is the list of values that make the property visible.

### `collection` — repeatable sub-objects

Use `type="collection"` with `fields` to model a list of structured items (e.g. a list
of HTTP headers with both a key and a value field):

```python
NodeProperty(
    name="headers",
    display_name="Headers",
    type="collection",
    fields=[
        NodeProperty(name="key", display_name="Header Name", type="string", required=True),
        NodeProperty(name="value", display_name="Header Value", type="string", required=True),
    ],
),
```

The frontend renders an "Add item" button; each item is an independent form group.

---

## Capability hooks

`BaseNode` exposes three class-level hooks that the executor reads to alter routing
behavior. Override them when your node has non-default data-flow semantics.

### `input_source`

```python
input_source: ClassVar[Literal["workflow_input", "previous_output"]] = "previous_output"
```

Controls where `node_input.data` comes from:
- `"previous_output"` (default) — the output dict of the preceding node.
- `"workflow_input"` — the original workflow invocation payload. Use this only for
  START-like nodes that ignore prior steps (the built-in `StartNode` sets this).

### `is_terminal`

```python
is_terminal: ClassVar[bool] = False
```

Set to `True` to signal that reaching this node ends the workflow run (like the
built-in `EndNode`). The executor stops traversal and records the final result.

### `get_branch_index`

```python
def get_branch_index(self, node_output: NodeOutput) -> int | None:
    return None
```

Override for branching nodes (like `ConditionNode`). Return the zero-based index of
the outgoing edge to follow. Return `None` (default) to follow the single outgoing
edge. The returned index selects among the edges defined in the workflow graph.

Example for a node with two branches (true / false):

```python
def get_branch_index(self, node_output: NodeOutput) -> int | None:
    return 0 if node_output.data.get("matched") else 1
```

---

## Frontend rendering

The frontend exposes two tiers of node UI:

**Generic renderer (default, no React code needed)**
Every node that returns a `NodeDescriptor` from `descriptor()` is drawn automatically
by the generic form renderer. It reads `descriptor().properties`, constructs the form
fields, and serializes the values back into the node's `config` dict. This is how
`DelayNode` and most plugin nodes work.

The catalog of available nodes is populated from `GET /api/nodes`, which calls
`NodeRegistry.get_descriptors()` and returns every descriptor in the registry. Adding a
new in-tree or plugin node automatically surfaces it in the sidebar without touching the
frontend.

**Custom widgets (opt-in, for complex nodes)**
Built-in nodes with rich UIs — Agent, Condition, HTTP Request — register dedicated React
components that render specialized editors (instruction lists, CEL condition builders,
etc.). This is not part of the public plugin API. If your node's configuration cannot be
adequately expressed through the property types above, open a discussion before building
a custom widget.

---

## Summary checklist

### In-tree node

- [ ] Create `assemblix-app-api/assemblix_api/nodes/my_node.py`
- [ ] Subclass `BaseNode`, decorate with `@register_node("my_type")`
- [ ] Implement `async def execute(self, node_input: NodeInput) -> NodeOutput`
- [ ] Override `descriptor()` to return a `NodeDescriptor` with `properties`
- [ ] Add `from .my_node import MyNode  # noqa: F401` to `assemblix_api/nodes/__init__.py`
- [ ] Add `"MyNode"` to `__all__` in the same file
- [ ] **No migration, no enum edit, no frontend change needed**

### Out-of-tree plugin

- [ ] Create a Python package with `@register_node`-decorated node classes
- [ ] Declare `[project.entry-points."assemblix.nodes"]` in `pyproject.toml`
- [ ] `pip install` the package into the backend's virtualenv
- [ ] Restart the backend — the plugin is auto-discovered and registered
