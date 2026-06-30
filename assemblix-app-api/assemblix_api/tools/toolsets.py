# /tools/toolsets.py
"""Building Pydantic AI toolsets for the agent node: function tools + MCP seam.

Tools and MCP servers are fed into `pydantic_ai.Agent(toolsets=[...])` through a
single mechanism. Our `BaseTool`s are wrapped into `pydantic_ai.Tool` using their
explicit JSON schema (`to_openai_format`), while MCP is so far only an architectural
seam (the config is accepted, a real client is not connected).
"""

from __future__ import annotations

import structlog
from pydantic_ai.tools import Tool
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from assemblix_api.tools import BaseTool
from assemblix_api.tools.registry import ToolContext, registry

logger = structlog.get_logger(__name__)


def to_pydantic_tool(base: BaseTool) -> Tool:
    """Wrap a `BaseTool` into a `pydantic_ai.Tool` using its OpenAI JSON schema."""
    spec = base.to_openai_format()["function"]

    async def _invoke(**kwargs: object) -> object:
        return await base.execute(**kwargs)

    return Tool.from_schema(
        _invoke,
        name=spec["name"],
        description=spec.get("description"),
        json_schema=spec["parameters"],
    )


def _build_mcp_toolsets(mcp_servers: list) -> list[AbstractToolset]:
    """MCP SEAM. The MCP server config is already accepted, but a real client is NOT
    connected yet (decision: only a backend seam, without UI).

    To enable — map each config into one of the native toolsets
    `pydantic_ai.mcp.MCPServerStreamableHTTP` / `MCPServerSSE` / `MCPServerStdio`
    and return the list. Everything else (passing into Agent) is already in place.
    """
    if mcp_servers:
        logger.info("agent.mcp_seam.configured_not_wired", count=len(mcp_servers))
    return []


def build_toolsets(
    tool_names: list[str] | None,
    mcp_servers: list | None,
    ctx: ToolContext,
) -> list[AbstractToolset]:
    """Build the list of toolsets for Agent: function tools + (seam) MCP.

    Unknown tool names are skipped with a warning (as before in the node).
    """
    toolsets: list[AbstractToolset] = []

    fn_tools: list[Tool] = []
    for name in tool_names or []:
        if not registry.is_registered(name):
            logger.warning("agent.tool_not_found", tool_name=name)
            continue
        fn_tools.append(to_pydantic_tool(registry.create(name, ctx)))

    if fn_tools:
        toolsets.append(FunctionToolset(fn_tools))

    toolsets.extend(_build_mcp_toolsets(mcp_servers or []))
    return toolsets
